import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Dashboard Oncológico", layout="wide")
st.title("📋 Relatório Consolidado - Pacientes Oncológicos")

# --- ESTILO CSS ---
st.markdown("""
<style>
    .dataframe {font-size: 13px !important;}
    th, td {text-align: center !important;}
    th {background-color: #f0f2f6;}
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES GERAIS ---

def clean_stage(val):
    if pd.isna(val): return None
    s = str(val).upper()
    match = re.search(r'\b(IV|III|II|I)\b', s)
    return match.group(1) if match else None

def calculate_time_years(row, col_inicio, col_obito, is_mieloma=False):
    try:
        start_date = row[col_inicio]
        obito_date = row[col_obito]
        
        if pd.isna(start_date): return None
        
        # Data de corte
        # Se for Mieloma, usamos data atual ou óbito
        # Se for Linfoma, mantemos a lógica anterior (ou 2025 se preferir, aqui deixei dinâmico para hoje)
        ref_date = pd.Timestamp.now()
        
        if pd.notna(obito_date):
            end_date = obito_date
        else:
            end_date = ref_date
            
        if start_date > end_date: return 0
        return (end_date - start_date).days / 365.25
    except:
        return None

# --- PROCESSAMENTO POR TIPO ---

def process_linfoma(df, fix_recidiva_year=None):
    # Identificar colunas (Linfoma geralmente header=7)
    # Busca flexível de colunas
    col_map = {
        'genero': [c for c in df.columns if 'GENERO' in c.upper()][0],
        'inicio': [c for c in df.columns if 'Data Primeira Consulta' in c][0],
        'idade': [c for c in df.columns if 'Idade' in c][0],
        'obito_flag': [c for c in df.columns if 'Óbito' in c][0],
        'recidiva_flag': [c for c in df.columns if 'Recidiva' in c][0],
        'estagio': [c for c in df.columns if 'Estadiamento' in c][0]
    }

    # Tratamento
    df['Data_Inicio'] = pd.to_datetime(df[col_map['inicio']], errors='coerce')
    df['Idade_Num'] = pd.to_numeric(df[col_map['idade']], errors='coerce')
    
    # Óbito no Linfoma muitas vezes é uma coluna com Data ou S/N. 
    # Assumindo que se tiver data na coluna de Óbito, é óbito.
    df['Data_Obito'] = pd.to_datetime(df[col_map['obito_flag']], errors='coerce')
    df['Is_Obito'] = df['Data_Obito'].notna()
    
    # Recidiva
    df['Is_Recidiva'] = df[col_map['recidiva_flag']].astype(str).str.strip().str.upper().isin(['S', 'SIM', 'YES'])
    
    # Se foi pedido para fixar ano (ex: 2025 para o arquivo 2)
    if fix_recidiva_year:
        df['Ano_Recidiva'] = np.where(df['Is_Recidiva'], fix_recidiva_year, np.nan)
    else:
        # Tenta achar data se existir
        col_rec_data = [c for c in df.columns if 'Data de Inicio do tratamento pós recidiva' in c]
        if col_rec_data:
            df['Ano_Recidiva'] = pd.to_datetime(df[col_rec_data[0]], errors='coerce').dt.year
        else:
            df['Ano_Recidiva'] = np.nan

    # Tempo
    df['Tempo_Anos'] = df.apply(lambda x: calculate_time_years(x, 'Data_Inicio', 'Data_Obito'), axis=1)
    
    # Estágio
    df['Estagio_Limpo'] = df[col_map['estagio']].apply(clean_stage)
    
    return df, col_map['genero']

def process_mieloma(df):
    # Identificar colunas (Mieloma geralmente header=2)
    col_map = {
        'genero': [c for c in df.columns if 'GENERO' in c.upper()][0],
        'inicio': [c for c in df.columns if 'Data Primeira Consulta' in c][0],
        'idade': [c for c in df.columns if 'Idade' in c][0],
        'obito_data': [c for c in df.columns if 'Data do óbito' in c or 'Data do obito' in c][0],
        'recidiva_flag': [c for c in df.columns if 'Recidiva' in c][0],
        'recidiva_data': [c for c in df.columns if 'DATA INICIO DA RETOMADA' in c][0]
    }

    # Tratamento
    df['Data_Inicio'] = pd.to_datetime(df[col_map['inicio']], errors='coerce')
    df['Idade_Num'] = pd.to_numeric(df[col_map['idade']], errors='coerce')
    
    # Óbito
    df['Data_Obito'] = pd.to_datetime(df[col_map['obito_data']], errors='coerce')
    df['Is_Obito'] = df['Data_Obito'].notna()
    
    # Recidiva (Data da Retomada indica o ano)
    df['Data_Recidiva'] = pd.to_datetime(df[col_map['recidiva_data']], errors='coerce')
    df['Ano_Recidiva'] = df['Data_Recidiva'].dt.year
    df['Is_Recidiva'] = df[col_map['recidiva_flag']].astype(str).str.strip().str.upper().isin(['S', 'SIM', 'YES'])

    # Tempo
    df['Tempo_Anos'] = df.apply(lambda x: calculate_time_years(x, 'Data_Inicio', 'Data_Obito', is_mieloma=True), axis=1)
    
    # Não tem Estadiamento
    df['Estagio_Limpo'] = None
    
    return df, col_map['genero']

# --- INTERFACE PRINCIPAL ---

st.sidebar.header("⚙️ Configurações")
tipo_analise = st.sidebar.selectbox(
    "Selecione o Tipo de Doença:",
    ["Linfomas (com Estadiamento)", "Mieloma Múltiplo (sem Estadiamento)"]
)

# Sugestão de Header baseada no tipo
default_header = 7 if "Linfomas" in tipo_analise else 2
header_row = st.sidebar.number_input("Linha do Cabeçalho (0-based)", value=default_header, min_value=0)

uploaded_file = st.sidebar.file_uploader("Carregar Arquivo", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # Leitura
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, header=header_row)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row, sep=';', encoding='latin1')
        else:
            df = pd.read_excel(uploaded_file, header=header_row)

        df.columns = df.columns.str.strip()

        # Processamento Condicional
        if "Linfomas" in tipo_analise:
            # Opção de fixar ano para Linfomas se desejar (como no pedido anterior)
            fixar_ano = st.sidebar.checkbox("Fixar ano de Recidiva como 2025?", value=False)
            ano_fixo = 2025 if fixar_ano else None
            
            df_proc, col_genero = process_linfoma(df, fix_recidiva_year=ano_fixo)
            show_estagio = True
        else:
            # Mieloma
            df_proc, col_genero = process_mieloma(df)
            show_estagio = False

        # --- GERAÇÃO DA TABELA FINAL ---
        
        def create_summary_row(sub_df, label):
            data = {'Gênero': label, 'Total': len(sub_df)}
            
            # 1. Idade
            age_bins = [0, 20, 40, 60, 80, 150]
            age_labels = ['≤20', '21-40', '41-60', '61-80', '>80']
            if not sub_df.empty:
                age_counts = pd.cut(sub_df['Idade_Num'], bins=age_bins, labels=age_labels).value_counts()
                for lbl in age_labels:
                    data[f'Idade ({lbl})'] = age_counts.get(lbl, 0)
            
            # 2. Tempo
            time_bins = [-1, 2, 5, 10, 100]
            time_labels = ['≤2 anos', '3-5 anos', '6-10 anos', '>10 Anos']
            if not sub_df.empty:
                time_counts = pd.cut(sub_df['Tempo_Anos'], bins=time_bins, labels=time_labels).value_counts()
                for lbl in time_labels:
                    data[f'Tempo ({lbl})'] = time_counts.get(lbl, 0)
            
            # 3. Estadiamento (Só para Linfomas)
            if show_estagio:
                est_counts = sub_df['Estagio_Limpo'].value_counts()
                for est in ['I', 'II', 'III', 'IV']:
                    data[f'Est. {est}'] = est_counts.get(est, 0)
            
            # 4. Óbitos
            data['Óbitos'] = sub_df['Is_Obito'].sum()
            
            # 5. Recidivas por Ano
            # Pega todos os anos encontrados no dataframe inteiro para criar colunas consistentes
            anos_possiveis = sorted(df_proc['Ano_Recidiva'].dropna().unique())
            anos_possiveis = [int(a) for a in anos_possiveis]
            
            for ano in anos_possiveis:
                qtd = len(sub_df[sub_df['Ano_Recidiva'] == ano])
                data[f'{ano} (Recidiva)'] = qtd
                
            # Se não houver anos (ex: ninguém recidivou ou sem datas), mostra total
            if not anos_possiveis:
                data['Recidivas (Total)'] = sub_df['Is_Recidiva'].sum()
                
            return data

        # Montar linhas
        rows = []
        rows.append(create_summary_row(df_proc[df_proc[col_genero].str.upper() == 'F'], 'F'))
        rows.append(create_summary_row(df_proc[df_proc[col_genero].str.upper() == 'M'], 'M'))
        rows.append(create_summary_row(df_proc, 'Total'))
        
        resumo_df = pd.DataFrame(rows).set_index('Gênero')
        
        st.subheader(f"Resultado: {tipo_analise}")
        st.dataframe(resumo_df, use_container_width=True)
        
        # Download
        csv = resumo_df.to_csv().encode('utf-8')
        st.download_button(f"💾 Baixar CSV ({tipo_analise})", csv, "relatorio.csv", "text/csv")
        
        # Debug (Opcional)
        with st.expander("Verificar Dados Brutos Processados"):
            cols_show = ['Nome', col_genero, 'Idade_Num', 'Tempo_Anos', 'Is_Obito', 'Ano_Recidiva']
            if show_estagio: cols_show.append('Estagio_Limpo')
            # Verifica colunas existentes antes de mostrar
            cols_final = [c for c in cols_show if c in df_proc.columns]
            st.dataframe(df_proc[cols_final].head(20))

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        st.info("Verifique se o 'Tipo de Doença' selecionado corresponde ao arquivo carregado (cabeçalhos diferentes).")
else:
    st.info("Aguardando arquivo...")
