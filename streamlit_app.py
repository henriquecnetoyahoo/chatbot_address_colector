import streamlit as st
import pandas as pd
import os
from datetime import datetime
import requests
import json
from langchain_ollama.llms import OllamaLLM
from langchain.prompts import PromptTemplate


# Set up the page title
st.title("Property Referral Collector")
st.write(
    "This is a simple chatbot that aims to collect Referral's address by Natural Language approach. "
)

# Initialize session state to store chat history and collected information
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Add an initial message from the assistant
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Olá! Sou um assistente para coletar informações de propriedades no Brasil. "
        "Por favor, forneça o endereço completo da propriedade e os dados do proprietario."
    })

if "property_info" not in st.session_state:
    st.session_state.property_info = {
        "logradouro": "",
        "number": "",
        "neighborhood": "",
        "city": "",
        "complement": "",
        "zip_code": "",
        "owner_name": "",
        "cell_phone": ""
    }

if "current_stage" not in st.session_state:
    st.session_state.current_stage = "address"

# Function to interact with Ollama via LangChain
def query_ollama(prompt, system_prompt=""):
    try:
        # Initialize the Ollama model using LangChain
        model = OllamaLLM(model="llama3.2")
        
        # Combine system prompt and user prompt if system prompt exists
        if system_prompt:
            template = """
            {system}
            
            User: {prompt}
            Assistant:
            """
            prompt_template = PromptTemplate(
                input_variables=["system", "prompt"],
                template=template
            )
            
            formatted_prompt = prompt_template.format(system=system_prompt, prompt=prompt)
            response = model.invoke(formatted_prompt)
        else:
            response = model.invoke(prompt)
            
        return response
    except Exception as e:
        st.error(f"Error communicating with Ollama: {str(e)}")
        return "Desculpe, tive um problema ao processar sua solicitação."

# Function to parse Brazilian address using Ollama
def parse_address(address_text):
    system_prompt = """
    You are an assistant to collect properties addresses from brazilian users. The properties to be collect will be houses 
or apartments in Brazil. Extract the following data: 
    - logradouro (street, avenue, etc.)
    - number
    - neighborhood
    - city
    - complement (if exists and only for apartments)
    - CEP (zip code)
    - property_type (house or apartment)

    Example, in this address "av. dr. altino arantes, 865, vila clementino, sao paulo, apto 174 bloco B, 04042-034", 
    logradouro is "av. dr. altino arantes", number is "865", neighborhood is "vila clementino", 
    city is "sao paulo", complement is "apto 174 bloco B" and zip code is "04042-034".
    
    Carry on the user to provide the property full address in portugues. After that, ask for two more infos:
     - owner_name (name of house or apartment owner)
     - owner_phone (cell phone of the owner)

    Finally, return the JSON object containing such informations. 
    Be concise to get all data from user.
    """
    
    prompt = f"Parse this Brazilian address and extract the components:: {address_text}"
    
    try:
        response = query_ollama(prompt, system_prompt)
        # Try to parse the response as JSON
        try:
            # Check if the response contains a JSON object
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                address_components = json.loads(json_str)
                return address_components
        except:
            # If JSON parsing fails, return None
            pass
        
        # If we couldn't parse JSON, return None
        return None
    except Exception as e:
        st.error(f"Error parsing address: {str(e)}")
        return None

# Function to save data to CSV
def save_to_csv():
    data = st.session_state.property_info.copy()
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    df = pd.DataFrame([data])
    file_exists = os.path.isfile('property_data.csv')
    
    if file_exists:
        df.to_csv('property_data.csv', mode='a', header=False, index=False)
    else:
        df.to_csv('property_data.csv', index=False)
    
    return "Informações salvas com sucesso!"

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Function to process user input based on current stage
def process_input(user_input):
    if st.session_state.current_stage == "address":
        # Try to parse the full address using Ollama
        address_components = parse_address(user_input)
        
        if address_components and all(k in address_components for k in ["logradouro", "number", "neighborhood", "city", "cep", "property_type", "owner_name", "owner_phone"]):
            # Successfully parsed the address
            st.session_state.property_info["logradouro"] = address_components.get("logradouro", "")
            st.session_state.property_info["number"] = address_components.get("number", "")
            st.session_state.property_info["neighborhood"] = address_components.get("neighborhood", "")
            st.session_state.property_info["city"] = address_components.get("city", "")
            st.session_state.property_info["complement"] = address_components.get("complement", "")
            st.session_state.property_info["zip_code"] = address_components.get("cep", "")
            st.session_state.property_info["property_type"] = address_components.get("property_type", "")
            st.session_state.property_info["owner_name"] = address_components.get("owner_name", "")
            st.session_state.property_info["owner_phone"] = address_components.get("owner_phone", "")
            
            # Move to next stage
            st.session_state.current_stage = "confirm_address"
            
            # Generate summary of parsed address
            info = st.session_state.property_info
            summary = f"""
            Entendi o seguinte endereço:
            
            Logradouro: {info['logradouro']}
            Número: {info['number']}
            Bairro: {info['neighborhood']}
            Cidade: {info['city']}
            Complemento: {info['complement'] if info['complement'] else 'Não informado'}
            CEP: {info['zip_code']}
            property_type: {info['property_type']}
            owner_name: {info['owner_name']}
            owner_phone: {info['owner_phone']}
            
            Estas informações estão corretas? Responda 'sim' para continuar ou 'não' para corrigir.
            """
            return summary
        else:
            # Couldn't parse the address automatically, ask for components one by one
            st.session_state.current_stage = "logradouro"
            return "Vamos coletar as informações do endereço uma a uma. Por favor, informe o logradouro (nome da rua, avenida, etc.):"
    
    elif st.session_state.current_stage == "confirm_address":
        if user_input.lower() in ["sim", "s", "yes", "y"]:
            st.session_state.current_stage = "owner_name"
            return "Ótimo! Agora, por favor, informe o nome do proprietário:"
        else:
            st.session_state.current_stage = "logradouro"
            return "Vamos corrigir as informações. Por favor, informe o logradouro (nome da rua, avenida, etc.):"
    
    elif st.session_state.current_stage == "logradouro":
        st.session_state.property_info["logradouro"] = user_input
        st.session_state.current_stage = "number"
        return "Por favor, informe o número do imóvel:"
    
    elif st.session_state.current_stage == "number":
        st.session_state.property_info["number"] = user_input
        st.session_state.current_stage = "neighborhood"
        return "Por favor, informe o bairro:"
    
    elif st.session_state.current_stage == "neighborhood":
        st.session_state.property_info["neighborhood"] = user_input
        st.session_state.current_stage = "city"
        return "Por favor, informe a cidade:"
    
    elif st.session_state.current_stage == "city":
        st.session_state.property_info["city"] = user_input
        st.session_state.current_stage = "complement"
        return "Por favor, informe o complemento (como 'apto 174 bloco B') ou digite 'nenhum' se for uma casa:"
    
    elif st.session_state.current_stage == "complement":
        st.session_state.property_info["complement"] = "" if user_input.lower() in ["nenhum", "none", "não", "nao"] else user_input
        st.session_state.current_stage = "zip_code"
        return "Por favor, informe o CEP:"
    
    elif st.session_state.current_stage == "zip_code":
        st.session_state.property_info["zip_code"] = user_input
        st.session_state.current_stage = "owner_name"
        return "Agora, por favor, informe o nome do proprietário:"
    
    elif st.session_state.current_stage == "owner_name":
        st.session_state.property_info["owner_name"] = user_input
        st.session_state.current_stage = "cell_phone"
        return "Por fim, informe o número de celular do proprietário:"
    
    elif st.session_state.current_stage == "cell_phone":
        st.session_state.property_info["cell_phone"] = user_input
        st.session_state.current_stage = "confirm"
        
        # Display all collected information
        info = st.session_state.property_info
        summary = f"""
        Aqui estão as informações fornecidas:
        
        Endereço: {info['logradouro']}, {info['number']}
        Bairro: {info['neighborhood']}
        Cidade: {info['city']}
        Complemento: {info['complement'] if info['complement'] else 'Não informado'}
        CEP: {info['zip_code']}
        Proprietário: {info['owner_name']}
        Telefone: {info['cell_phone']}
        
        Estas informações estão corretas? Digite 'sim' para salvar ou 'não' para recomeçar.
        """
        return summary
    
    elif st.session_state.current_stage == "confirm":
        if user_input.lower() in ["sim", "s", "yes", "y"]:
            result = save_to_csv()
            st.session_state.current_stage = "address"
            # Reset property info for next entry
            st.session_state.property_info = {
                "logradouro": "",
                "number": "",
                "neighborhood": "",
                "city": "",
                "complement": "",
                "zip_code": "",
                "owner_name": "",
                "cell_phone": ""
            }
            return f"{result} Deseja cadastrar outro imóvel? Digite 'sim' para continuar ou 'não' para finalizar."
        else:
            st.session_state.current_stage = "address"
            return "Vamos recomeçar. Por favor, forneça o endereço completo do imóvel."

# Process the input and get response
if prompt := st.chat_input("Digite aqui..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Process the input and get response - improved implementation
    response_container = st.empty()
    with response_container:
        with st.spinner("Processando..."):
            response = process_input(prompt)
    
    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.write(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})