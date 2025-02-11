from typing import Dict, List
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.llms import LLM
from ..base_classes import LLMConfig
from ..constants.str_literals import InstallLibs, LLMLiterals, LLMOutputTypes
from .llm_helper import get_token_counter
from ..exceptions import GlueLLMException
from ..utils.runtime_tasks import install_lib_if_missing
from ..utils.logging import get_glue_logger
from ..utils.runtime_tasks import str_to_class
from .llm_settings import (
    use_openai_api_key,
    get_openai_config,
    get_azure_config,
    get_model_type,
    get_ollama_config,
)

logger = get_glue_logger(__name__)

def dict_to_chat_messages(messages_dict: Dict) -> List[ChatMessage]:
    """
    Convert a dictionary of messages (e.g. {"messages": [{"role": "user", "content": "..."}]})
    into a list of ChatMessage objects from llama_index.
    """
    if "messages" not in messages_dict:
        raise ValueError("Expected 'messages' key in the dictionary.")

    chat_messages = []
    for msg in messages_dict["messages"]:
        role_str = msg.get("role", "user").lower()
        if role_str == "assistant":
            role = MessageRole.ASSISTANT
        elif role_str == "system":
            role = MessageRole.SYSTEM
        else:
            role = MessageRole.USER

        # create ChatMessage
        chat_msg = ChatMessage(role=role, content=msg.get("content", ""))
        chat_messages.append(chat_msg)
    return chat_messages

def _call_openai_api(messages):
    """
    Specialized function for calling an OpenAI-like endpoint using
    environment-based config from llm_settings.
    """
    from openai import OpenAI
    openai_cfg = get_openai_config()
    
    chat_messages = dict_to_chat_messages(messages)
    
    api_key = openai_cfg["api_key"]
    model_name = openai_cfg["model_name"]
    temp = openai_cfg["temperature"]

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": m.role.value, "content": m.content} for m in chat_messages],
            temperature=temp,
        )
        prediction = response.choices[0].message.content
        return prediction

    except Exception as e:
        logger.error(f"Error in _call_openai_api: {e}")
        raise GlueLLMException("Error calling OpenAI API") from e

def _call_azure_api(messages):
    """
    Specialized function for calling Azure OpenAI endpoint using
    environment-based config from llm_settings.
    """
    from openai import AzureOpenAI
    from azure.identity import get_bearer_token_provider, AzureCliCredential
    azure_cfg = get_azure_config()

    token_provider = get_bearer_token_provider(
        AzureCliCredential(),
        "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        api_version=azure_cfg["api_version"],
        azure_endpoint=azure_cfg["azure_endpoint"],
        azure_ad_token_provider=token_provider
    )
    response = client.chat.completions.create(
        model=azure_cfg["deployment_name"],
        messages=messages,
        temperature=azure_cfg["temperature"],
    )
    prediction = response.choices[0].message.content
    return prediction

def _call_ollama_api(messages):
    """
    Specialized function for calling Ollama endpoint using environment-based config.
    """
    from llama_index.llms.ollama import Ollama
    cfg = get_ollama_config()

    chat_messages = dict_to_chat_messages(messages)

    ollama_client = Ollama(
        base_url=cfg["base_url"],
        model=cfg["model_name"],
        temperature=cfg["temperature"],
    )

    response = ollama_client.chat(chat_messages)
    return response.message.content if response.message else ""


def env_based_chat_completion(messages):
    """
    Decide which provider to use based on environment config in llm_settings.
    """
    provider = get_model_type()
    if provider == "Ollama":
        return _call_ollama_api(messages)
    elif use_openai_api_key():
        return _call_openai_api(messages)
    else:
        return _call_azure_api(messages)

class LLMMgr:

    @staticmethod
    def _handle_llm_error(e: Exception, provider_name: str, messages: Dict) -> str:
        logger.error(f"Exception with {provider_name} on messages {messages}: {e}")
        return "Sorry, I am not able to understand your query. Please try again."

    @staticmethod
    def chat_completion(messages: Dict) -> str:
        llm_handle = get_model_type()
        try:
            return env_based_chat_completion(messages)
        except Exception as e:
            return LLMMgr._handle_llm_error(e, llm_handle, messages)
        

    @staticmethod
    def get_all_model_ids_of_type(llm_config: LLMConfig, llm_output_type: str):
        res = []
        if llm_config.azure_open_ai:
            for azure_model in llm_config.azure_open_ai.azure_oai_models:
                if azure_model.model_type == llm_output_type:
                    res.append(azure_model.unique_model_id)
        if llm_config.custom_models:
            if llm_config.custom_models.model_type == llm_output_type:
                res.append(llm_config.custom_models.unique_model_id)
        return res

    @staticmethod
    def get_llm_pool(llm_config: LLMConfig) -> Dict[str, LLM]:
        """
        Create a dictionary of LLMs. key would be unique id of LLM, value is object using which
        methods associated with that LLM service can be called.

        :param llm_config: Object having all settings & preferences for all LLMs to be used in out system
        :return: Dict key=unique_model_id of LLM, value=Object of class llama_index.core.llms.LLM
        which can be used as handle to that LLM
        """

        def maybe_add_token_counter(track_tokens: bool, model_name: str):
            """
            If track_tokens is True, returns a CallbackManager with TokenCountingHandler.
            Otherwise, returns None.
            """
            if not track_tokens:
                return None
            token_counter = TokenCountingHandler(
                tokenizer=tiktoken.encoding_for_model(model_name).encode
            )
            mgr = CallbackManager([token_counter])
            token_counter.reset_counts()
            return mgr

        llm_pool = {}
        az_llm_config = llm_config.azure_open_ai

        if az_llm_config:
            install_lib_if_missing(InstallLibs.LLAMA_LLM_AZ_OAI)
            install_lib_if_missing(InstallLibs.LLAMA_EMB_AZ_OAI)
            install_lib_if_missing(InstallLibs.LLAMA_MM_LLM_AZ_OAI)
            install_lib_if_missing(InstallLibs.TIKTOKEN)

            import tiktoken
            # from llama_index.llms.azure_openai import AzureOpenAI
            from openai import AzureOpenAI
            from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
            from llama_index.multi_modal_llms.azure_openai import AzureOpenAIMultiModal

            az_token_provider = None
            # if az_llm_config.use_azure_ad:
            from azure.identity import get_bearer_token_provider, AzureCliCredential
            az_token_provider = get_bearer_token_provider(AzureCliCredential(),
                                                        "https://cognitiveservices.azure.com/.default")

            for azure_oai_model in az_llm_config.azure_oai_models:
                callback_mgr = None

                callback_mgr = maybe_add_token_counter(
                    track_tokens=azure_oai_model.track_tokens,
                    model_name=azure_oai_model.model_name_in_azure
                )

                if azure_oai_model.model_type in [LLMOutputTypes.CHAT, LLMOutputTypes.COMPLETION]:
                    llm_pool[azure_oai_model.unique_model_id] = \
                        AzureOpenAI(
                                    azure_ad_token_provider=az_token_provider,
                                    api_key=az_llm_config.api_key,
                                    azure_endpoint=az_llm_config.azure_endpoint,
                                    api_version=az_llm_config.api_version,
                                    )

                elif azure_oai_model.model_type == LLMOutputTypes.EMBEDDINGS:
                    llm_pool[azure_oai_model.unique_model_id] =\
                        AzureOpenAIEmbedding(use_azure_ad=az_llm_config.use_azure_ad,
                                             azure_ad_token_provider=az_token_provider,
                                             model=azure_oai_model.model_name_in_azure,
                                             deployment_name=azure_oai_model.deployment_name_in_azure,
                                             api_key=az_llm_config.api_key,
                                             azure_endpoint=az_llm_config.azure_endpoint,
                                             api_version=az_llm_config.api_version,
                                             callback_manager=callback_mgr
                                             )
                elif azure_oai_model.model_type == LLMOutputTypes.MULTI_MODAL:

                    llm_pool[azure_oai_model.unique_model_id] = \
                        AzureOpenAIMultiModal(use_azure_ad=az_llm_config.use_azure_ad,
                                              azure_ad_token_provider=az_token_provider,
                                              model=azure_oai_model.model_name_in_azure,
                                              deployment_name=azure_oai_model.deployment_name_in_azure,
                                              api_key=az_llm_config.api_key,
                                              azure_endpoint=az_llm_config.azure_endpoint,
                                              api_version=az_llm_config.api_version,
                                              max_new_tokens=4096
                                              )

        if llm_config.custom_models:
            for custom_model in llm_config.custom_models:
                # try:
                custom_llm_class = str_to_class(custom_model.class_name, None, custom_model.path_to_py_file)

                callback_mgr = None
                if custom_model.track_tokens:
                    # If we need to count number of tokens used in LLM calls
                    token_counter = TokenCountingHandler(
                        tokenizer=custom_llm_class.get_tokenizer()
                        )
                    callback_mgr = CallbackManager([token_counter])
                    token_counter.reset_counts()
                llm_pool[custom_model.unique_model_id] = custom_llm_class(callback_manager=callback_mgr)
                # except Exception as e:
                    # raise GlueLLMException(f"Custom model {custom_model.unique_model_id} not loaded.", e)
        return llm_pool

    @staticmethod
    def get_tokens_used(llm_handle: LLM) -> Dict[str, int]:
        """
        For a given LLM, output the number of tokens used.

        :param llm_handle: Handle to a single LLM
        :return: Dict of token-type and count of tokens used
        """
        token_counter = get_token_counter(llm_handle)
        if token_counter:
            return {
                LLMLiterals.EMBEDDING_TOKEN_COUNT: token_counter.total_embedding_token_count,
                LLMLiterals.PROMPT_LLM_TOKEN_COUNT: token_counter.prompt_llm_token_count,
                LLMLiterals.COMPLETION_LLM_TOKEN_COUNT: token_counter.completion_llm_token_count,
                LLMLiterals.TOTAL_LLM_TOKEN_COUNT: token_counter.total_llm_token_count
                }
        return None
