import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Relatório de Pacientes 2025", layout="wide")
st.title("📋 Relatório Consolidado - Dados Oncológicos")

# --- ESTILO CSS ---
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
    try:
        start_date = row['Data Primeira Consulta']
        obito_date = row['Data_Obito_Valida']
        
        if pd.isna(start_date): return None
        
        # Data final: Se morreu, usa data óbito. Se vivo, usa hoje (ou fim de 2024/2025)
        end_date = pd.Timestamp("2025-12-31") 
        if pd.notna(obito_date):
            end_date = obito_date
            
        if start_date > end_date: return 0
        return (end_date - start_date).days / 365.25
    except:
        return None

# --- CARREGAMENTO ---
st.sidebar.header("📁 Importar Arquivo")
uploaded_file = st.sidebar.file_uploader("Selecione o arquivo CSV ou Excel", type=["csv", "xlsx"])
header_row = st.sidebar.number_input("Linha do Cabeçalho", value=7, min_value=0)

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
        
        # --- PROCESSAMENTO ---
        
        # Datas e Idade
        if 'Data Primeira Consulta' in df.columns:
            df['Data Primeira Consulta'] = pd.to_datetime(df['Data Primeira Consulta'], errors='coerce')
        
        df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')
        
        # Identificar colunas chaves
        col_obito = [c for c in df.columns if 'Óbito' in c][0]
        col_recidiva_flag = [c for c in df.columns if 'Recidiva (S) ou (N)' in c][0]
        # Data Recidiva (opcional, pois você forçou 2025)
        col_recidiva_data = [c for c in df.columns if 'Data de Inicio do tratamento pós recidiva' in c]

        # Tratar Óbito
        df['Data_Obito_Valida'] = pd.to_datetime(df[col_obito], errors='coerce')
        df['Is_Obito'] = df['Data_Obito_Valida'].notna()
        
        # Tratar Recidiva
        # Normaliza 'S', 's', 'Sim' para True
        df['Is_Recidiva'] = df[col_recidiva_flag].astype(str).str.strip().str.upper().isin(['S', 'SIM', 'YES'])
        
        # ** FORÇAR ANO 2025 SE FOR RECIDIVA **
        # Se a pessoa tem recidiva marcada (S), consideramos para a coluna 2025
        df['Ano_Recidiva_Considerado'] = np.where(df['Is_Recidiva'], 2025, np.nan)

        # Tempo (recalculado com base na data atual/óbito)
        df['Tempo_Anos'] = df.apply(calculate_time_years, axis=1)
        
        # Estadiamento
        col_estagio = [c for c in df.columns if 'Estadiamento' in c][0]
        df['Estagio_Limpo'] = df[col_estagio].apply(clean_stage)

        # --- TABELA RESUMO ---
        
        def create_summary_row(sub_df, label):
            # 1. Totais
            total = len(sub_df)
            
            # 2. Idade
            age_bins = [0, 20, 40, 60, 80, 150]
            age_labels = ['≤20', '21-40', '41-60', '61-80', '>80']
            if not sub_df.empty and sub_df['Idade'].notna().any():
                age_counts = pd.cut(sub_df['Idade'], bins=age_bins, labels=age_labels).value_counts()
            else:
                age_counts = pd.Series(0, index=age_labels)

            # 3. Tempo Tratamento
            time_bins = [-1, 2, 5, 10, 100]
            time_labels = ['≤2 anos', '3-5 anos', '6-10 anos', '>10 Anos']
            if not sub_df.empty and sub_df['Tempo_Anos'].notna().any():
                time_counts = pd.cut(sub_df['Tempo_Anos'], bins=time_bins, labels=time_labels).value_counts()
            else:
                time_counts = pd.Series(0, index=time_labels)

            # 4. Estadiamento
            est_counts = sub_df['Estagio_Limpo'].value_counts()

            # 5. Óbito e Recidiva
            obitos = sub_df['Is_Obito'].sum()
            recidiva_2025 = len(sub_df[sub_df['Ano_Recidiva_Considerado'] == 2025])
            
            return {
                'Gênero': label,
                'Linfomas (Total)': total,
                # Idade
                'Idade (≤20)': age_counts.get('≤20', 0),
                'Idade (21-40)': age_counts.get('21-40', 0),
                'Idade (41-60)': age_counts.get('41-60', 0),
                'Idade (61-80)': age_counts.get('61-80', 0),
                'Idade (>80)': age_counts.get('>80', 0),
                # Tempo
                'Tempo (≤2 anos)': time_counts.get('≤2 anos', 0),
                'Tempo (3-5 anos)': time_counts.get('3-5 anos', 0),
                'Tempo (6-10 anos)': time_counts.get('6-10 anos', 0),
                'Tempo (>10 Anos)': time_counts.get('>10 Anos', 0),
                # Estágio
                'Est. I': est_counts.get('I', 0),
                'Est. II': est_counts.get('II', 0),
                'Est. III': est_counts.get('III', 0),
                'Est. IV': est_counts.get('IV', 0),
                # Desfechos
                'Óbitos': obitos,
                '2025 (Recidiva)': recidiva_2025
            }

        rows = []
        rows.append(create_summary_row(df[df['GENERO'] == 'F'], 'F'))
        rows.append(create_summary_row(df[df['GENERO'] == 'M'], 'M'))
        rows.append(create_summary_row(df, 'Total'))
        
        resumo_df = pd.DataFrame(rows).set_index('Gênero')
        
        st.write("### Tabela Consolidada (2025)")
        st.dataframe(resumo_df, use_container_width=True)
        
        # Download
        st.download_button("💾 Baixar Tabela CSV", resumo_df.to_csv().encode('utf-8'), "relatorio_2025.csv", "text/csv")

    except Exception as e:
        st.error(f"Erro: {e}")

else:
    st.info("Aguardando arquivo...")
