import os
import json
import time
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file"
]

NOME_DOCUMENTO_PADRAO = "Diário de Sonhos"
ARQUIVO_CREDENCIAIS = "credentials.json"
ARQUIVO_TOKEN = "token.json"


def autenticar_google() -> Credentials:
    """Realiza o fluxo de autenticação OAuth 2.0 e salva/atualiza o token de acesso."""
    creds = None
    if os.path.exists(ARQUIVO_TOKEN):
        creds = Credentials.from_authorized_user_file(ARQUIVO_TOKEN, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(ARQUIVO_CREDENCIAIS):
                raise FileNotFoundError(
                    f"❌ '{ARQUIVO_CREDENCIAIS}' não encontrado na pasta raiz!\n"
                    "Baixe as credenciais OAuth no Google Cloud Console e salve nessa pasta."
                )
            flow = InstalledAppFlow.from_client_secrets_file(ARQUIVO_CREDENCIAIS, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(ARQUIVO_TOKEN, "w") as token_file:
            token_file.write(creds.to_json())
            
    return creds


def obter_ou_criar_documento(docs_service, drive_service, titulo_doc: str) -> tuple[str, str]:
    """
    Busca o documento pelo título no Google Drive. Se não existir, cria um novo.
    Retorna uma tupla: (doc_id, url_documento)
    """
    query = f"name = '{titulo_doc}' and mimeType = 'application/vnd.google-apps.document' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        doc_id = files[0]["id"]
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"📄 Documento encontrado no Google Drive! (ID: {doc_id})")
        return doc_id, doc_url
    else:
        doc = docs_service.documents().create(body={"title": titulo_doc}).execute()
        doc_id = doc.get("documentId")
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"✨ Novo documento '{titulo_doc}' criado com sucesso no Google Drive! (ID: {doc_id})")
        return doc_id, doc_url


def obter_ou_criar_guia_por_data(docs_service, doc_id: str, nome_data: str) -> tuple[str, int]:
    """
    Garante que a 1ª aba seja reservada para '📌 Índice & Análises' apenas uma vez.
    Cria ou localiza a aba específica para a data do sonho informado.
    """
    documento = docs_service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    tabs = documento.get("tabs", [])

    # 1. Checa a primeira aba para garantir a introdução SEM duplicar
    if tabs:
        primeira_tab = tabs[0]
        tab_id_primeira = primeira_tab.get("tabProperties", {}).get("tabId")
        body_content = primeira_tab.get("documentTab", {}).get("body", {}).get("content", [])
        
        # Extrai o texto acumulado na 1ª aba para verificar se o título já existe
        texto_acumulado_1a_aba = ""
        for elem in body_content:
            paragraph = elem.get("paragraph")
            if paragraph:
                for el in paragraph.get("elements", []):
                    texto_acumulado_1a_aba += el.get("textRun", {}).get("content", "")

        # Só insere o cabeçalho se ele ainda NÃO estiver presente na 1ª aba
        if "📌 DIÁRIO DE SONHOS" not in texto_acumulado_1a_aba:
            print("📌 Configurando 1ª aba para 'Índice & Análises' pela primeira vez...")
            texto_intro = "📌 DIÁRIO DE SONHOS — ÍNDICE & ANÁLISES\n\nEsta aba é reservada para resumos, mapeamento de tags e sínteses do agente analítico.\n\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{
                    "insertText": {
                        "location": {"index": 1, "tabId": tab_id_primeira},
                        "text": texto_intro
                    }
                }]}
            ).execute()

    # 2. Busca se a aba para a data especificada já existe
    for tab in tabs:
        tab_properties = tab.get("tabProperties", {})
        if tab_properties.get("title") == nome_data:
            tab_id = tab_properties.get("tabId")
            body_content = tab.get("documentTab", {}).get("body", {}).get("content", [])
            end_index = body_content[-1].get("endIndex", 1) - 1 if body_content else 1
            print(f"📌 Guia '{nome_data}' encontrada (Tab ID: {tab_id}).")
            return tab_id, end_index

    # 3. Cria uma nova aba para a data do sonho
    print(f"✨ Criando nova guia de data: '{nome_data}'...")
    req_add_tab = {
        "addDocumentTab": {
            "tabProperties": {
                "title": nome_data
            }
        }
    }
    
    response = docs_service.documents().batchUpdate(
        documentId=doc_id, 
        body={"requests": [req_add_tab]}
    ).execute()

    new_tab = response.get("replies", [])[0].get("addDocumentTab", {}).get("tabProperties", {})
    tab_id = new_tab.get("tabId")
    
    return tab_id, 1

def adicionar_sonho_em_guia(
    docs_service, 
    doc_id: str, 
    data_apenas: str, 
    hora_apenas: str, 
    texto_refinado: str, 
    id_audio: str = None
):
    """Insere o relato na guia correspondente à data no Google Docs."""
    tab_id, index_insercao = obter_ou_criar_guia_por_data(docs_service, doc_id, data_apenas)

    titulo_secao = f"🗓️ Registrado às {hora_apenas}\n"
    if id_audio:
        titulo_secao = f"🗓️ {id_audio} — Registrado às {hora_apenas}\n"

    corpo_texto = f"{texto_refinado}\n"
    divisor = "⎯" * 40 + "\n\n"

    texto_completo = f"{titulo_secao}{corpo_texto}{divisor}"

    requests = [
        {
            "insertText": {
                "location": {
                    "index": index_insercao,
                    "tabId": tab_id
                },
                "text": texto_completo
            }
        }
    ]

    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    print(f"✅ Sonho publicado com sucesso na guia '{data_apenas}'!")


def publicar_sonho_no_docs(
    texto_refinado: str, 
    nome_identificador: str = "Novo Sonho", 
    data_hora: time.struct_time = None
) -> str:
    """
    Função principal exportável para integrar com outros scripts do pipeline.
    Recebe o texto refinado do Gemini e envia para a aba correspondente no Google Docs.
    """
    if data_hora is None:
        data_hora = time.localtime()

    data_apenas = time.strftime("%d/%m/%Y", data_hora)
    hora_apenas = time.strftime("%H:%M", data_hora)

    creds = autenticar_google()
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # 1. Obtém/cria o diário e gera o link
    doc_id, doc_url = obter_ou_criar_documento(docs_service, drive_service, NOME_DOCUMENTO_PADRAO)

    # 2. Publica o sonho na guia da data
    adicionar_sonho_em_guia(
        docs_service=docs_service,
        doc_id=doc_id,
        data_apenas=data_apenas,
        hora_apenas=hora_apenas,
        texto_refinado=texto_refinado,
        id_audio=nome_identificador
    )

    return doc_url


def main():
    try:
        print("🔐 Autenticando com a API do Google...")
        creds = autenticar_google()
        
        docs_service = build("docs", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # 1. Localiza ou cria o documento principal
        doc_id, doc_url = obter_ou_criar_documento(docs_service, drive_service, NOME_DOCUMENTO_PADRAO)

        data_hoje = time.strftime("%d/%m/%Y")
        hora_atual = time.strftime("%H:%M")

        exemplo_texto_refinado = (
            "Eu tive um sonho em que caminhava por um parque antigo perto da praia. "
            "Encontrei pessoas conhecidas do passado e conversamos bastante sobre projetos antigos..."
        )

        print(f"\n🚀 Adicionando relato na guia do dia {data_hoje}...")
        adicionar_sonho_em_guia(
            docs_service=docs_service,
            doc_id=doc_id,
            data_apenas=data_hoje,
            hora_apenas=hora_atual,
            texto_refinado=exemplo_texto_refinado,
            id_audio="Sonho do Parque"
        )

        print("\n" + "=" * 60)
        print("🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
        print(f"🔗 Link direto para o diário: {doc_url}")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Erro na execução: {e}")


if __name__ == "__main__":
    main()