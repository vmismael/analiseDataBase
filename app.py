import streamlit as st
import pandas as pd
import numpy as np
import re

# Configuração da Página
st.set_page_config(page_title="Relatório Oncológico", layout="wide")
st.title("📋 Relatório Consolidado - Pacientes Oncológicos")

# --- ESTILIZAÇÃO ---
st.markdown("""
<style>
    .dataframe {font-size: 13px !important;}
    th, td {text-align: center !important;}
    th {background-color: #f0f2f6;}
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---

def clean_stage(val):
    if pd.isna(val): return None
    s = str(val).upper()
    match = re.search(r'\b(IV|III|II|I)\b', s)
    return match.group(1) if match else None

def calculate_time_years(row):
    """Calcula tempo de tratamento até 2025 ou até o óbito."""
    try:
        # Tenta achar a coluna de início (pode variar o nome)
        start_date = row.get('Data Primeira Consulta')
        
        # Data final: Se morreu, usa data óbito. Se vivo, usa fim de 2025.
        obito_date = row.get('Data_Obito_Valida')
        
        if pd.isna(start_date): return None
        
        end_date = pd.Timestamp("2025-12-31")
        if pd.notna(obito_date):
            end_date = obito_date
            
        if start_date > end_date: return 0
        return (end_date - start_date).days / 365.25
    except:
        return None

# --- BARRA LATERAL ---
st.sidebar.header("Configuração")

# 1. Seletor de Doença
doenca_selecionada = st.sidebar.selectbox(
    "Selecione a Doença",
    ("Linfomas", "Mieloma Múltiplo")
)

# Define a linha do cabeçalho automaticamente (0-based index)
# Linfoma: Linha 7 do Excel -> index 7 no pandas? O usuário disse "na 7". 
# Geralmente "linha 7" visual é index 6, mas no arquivo anterior usamos 7. Vamos manter o padrão.
if doenca_selecionada == "Linfomas":
    default_header = 7 
else:
    default_header = 2 

# 2. Upload
uploaded_file = st.sidebar.file_uploader(f"Carregue o arquivo de {doenca_selecionada}", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # Leitura do Arquivo
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, header=default_header)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=default_header, sep=';', encoding='latin1')
        else:
            df = pd.read_excel(uploaded_file, header=default_header)

        # Limpeza dos nomes das colunas
        df.columns = df.columns.str.strip()
        
        # --- PROCESSAMENTO COMUM ---
        
        # 1. Datas e Idade
        if 'Data Primeira Consulta' in df.columns:
            df['Data Primeira Consulta'] = pd.to_datetime(df['Data Primeira Consulta'], errors='coerce')
        
        if 'Idade' in df.columns:
            df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')
            
        # 2. Identificar Óbito (procura por colunas de data de óbito ou flag S/N)
        # Tenta encontrar coluna com 'Data' e 'óbito' no nome
        cols_data_obito = [c for c in df.columns if 'Data' in c and 'óbito' in c.lower()]
        cols_flag_obito = [c for c in df.columns if 'Óbito' in c and 'Data' not in c]
        
        df['Data_Obito_Valida'] = pd.NaT
        
        if cols_data_obito:
            # Se tem coluna de data explícita (comum no Mieloma)
            df['Data_Obito_Valida'] = pd.to_datetime(df[cols_data_obito[0]], errors='coerce')
            df['Is_Obito'] = df['Data_Obito_Valida'].notna()
        elif cols_flag_obito:
            # Se tem apenas flag S/N (comum no Linfoma, onde a data pode estar separada)
            # Aqui assumimos que se tem S na flag, conta como óbito, mas sem data precisa usa 2025 no tempo (limitação)
            # A menos que exista uma coluna separada de data que não achamos.
            # No arquivo anterior de linfoma, o óbito estava numa coluna S/N.
            df['Is_Obito'] = df[cols_flag_obito[0]].astype(str).str.strip().str.upper().isin(['S', 'SIM'])
        else:
            df['Is_Obito'] = False

        # 3. Identificar Recidiva
        cols_recidiva = [c for c in df.columns if 'Recidiva' in c and '(S) ou (N)' in c]
        if cols_recidiva:
            df['Is_Recidiva'] = df[cols_recidiva[0]].astype(str).str.strip().str.upper().isin(['S', 'SIM'])
        else:
            df['Is_Recidiva'] = False
            
        # Coluna fixa 2025 para recidiva
        df['Ano_Recidiva_Considerado'] = np.where(df['Is_Recidiva'], 2025, np.nan)

        # 4. Calcular Tempo
        df['Tempo_Anos'] = df.apply(calculate_time_years, axis=1)

        # --- PROCESSAMENTO ESPECÍFICO (ESTADIAMENTO) ---
        tem_estadiamento = False
        if doenca_selecionada == "Linfomas":
            col_estagio = [c for c in df.columns if 'Estadiamento' in c]
            if col_estagio:
                df['Estagio_Limpo'] = df[col_estagio[0]].apply(clean_stage)
                tem_estadiamento = True

        # --- GERAÇÃO DA TABELA ---
        
        def create_summary_row(sub_df, label):
            data = {'Gênero': label, 'Total': len(sub_df)}
            
            # Idade
            age_bins = [0, 20, 40, 60, 80, 150]
            age_labels = ['≤20', '21-40', '41-60', '61-80', '>80']
            if not sub_df.empty and 'Idade' in sub_df and sub_df['Idade'].notna().any():
                age_counts = pd.cut(sub_df['Idade'], bins=age_bins, labels=age_labels).value_counts()
            else:
                age_counts = pd.Series(0, index=age_labels)
            
            for lbl in age_labels:
                data[f'Idade ({lbl})'] = age_counts.get(lbl, 0)

            # Tempo
            time_bins = [-1, 2, 5, 10, 100]
            time_labels = ['≤2 anos', '3-5 anos', '6-10 anos', '>10 Anos']
            if not sub_df.empty and 'Tempo_Anos' in sub_df and sub_df['Tempo_Anos'].notna().any():
                time_counts = pd.cut(sub_df['Tempo_Anos'], bins=time_bins, labels=time_labels).value_counts()
            else:
                time_counts = pd.Series(0, index=time_labels)
            
            for lbl in time_labels:
                data[f'Tempo ({lbl})'] = time_counts.get(lbl, 0)

            # Estadiamento (Só para Linfomas)
            if tem_estadiamento:
                est_counts = sub_df['Estagio_Limpo'].value_counts()
                data['Est. I'] = est_counts.get('I', 0)
                data['Est. II'] = est_counts.get('II', 0)
                data['Est. III'] = est_counts.get('III', 0)
                data['Est. IV'] = est_counts.get('IV', 0)

            # Desfechos
            data['Óbitos'] = sub_df['Is_Obito'].sum()
            data['2025 (Recidiva)'] = len(sub_df[sub_df['Ano_Recidiva_Considerado'] == 2025])
            
            return data

        # Criar linhas (F, M, Total)
        rows = []
        if 'GENERO' in df.columns:
            rows.append(create_summary_row(df[df['GENERO'] == 'F'], 'F'))
            rows.append(create_summary_row(df[df['GENERO'] == 'M'], 'M'))
        else:
            st.warning("Coluna 'GENERO' não encontrada.")
            
        rows.append(create_summary_row(df, 'Total'))
        
        # DataFrame Final
        resumo_df = pd.DataFrame(rows)
        if not resumo_df.empty:
            resumo_df.set_index('Gênero', inplace=True)
        
        # Exibição
        st.subheader(f"Resumo: {doenca_selecionada}")
        st.dataframe(resumo_df, use_container_width=True)
        
        # Download
        nome_arquivo = f"resumo_{doenca_selecionada.lower().replace(' ', '_')}.csv"
        st.download_button("💾 Baixar Tabela CSV", resumo_df.to_csv().encode('utf-8'), nome_arquivo, "text/csv")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        st.info("Verifique se o arquivo corresponde à doença selecionada e se o formato das colunas está correto.")

else:
    st.info(f"Aguardando arquivo de **{doenca_selecionada}**.")
