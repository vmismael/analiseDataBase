import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

st.set_page_config(page_title="Relatório Oncológico", layout="wide")
st.title("📋 Relatório Consolidado - Pacientes Oncológicos")

# --- CSS PARA ESTILIZAR A TABELA ---
st.markdown("""
<style>
    .dataframe {font-size: 14px !important;}
    th {background-color: #f0f2f6; text-align: center !important;}
    td {text-align: center !important;}
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---

def clean_stage(val):
    """Extrai apenas o número romano do estadiamento (I, II, III, IV)"""
    if pd.isna(val): return None
    s = str(val).upper()
    match = re.search(r'\b(IV|III|II|I)\b', s)
    return match.group(1) if match else None

def check_keyword(row, keywords):
    """Verifica se alguma palavra-chave aparece em qualquer coluna de texto da linha"""
    row_str = " ".join([str(val).lower() for val in row.values])
    return any(k in row_str for k in keywords)

def calculate_treatment_time(start_date):
    """Calcula anos até o final de 2024"""
    ref_date = pd.Timestamp("2024-12-31")
    if pd.isna(start_date): return None
    if start_date > ref_date: return 0
    return (ref_date - start_date).days / 365.25

# --- CARREGAMENTO ---
st.sidebar.header("📁 Upload de Dados")
uploaded_file = st.sidebar.file_uploader("Arraste seu arquivo Excel/CSV aqui", type=["xlsx", "csv"])
skip_rows = st.sidebar.number_input("Linhas de cabeçalho para pular", value=7, min_value=0)

if uploaded_file:
    try:
        # Leitura do arquivo
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, skiprows=skip_rows)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, skiprows=skip_rows, sep=';', encoding='latin1')
        else:
            df = pd.read_excel(uploaded_file, skiprows=skip_rows)

        # Limpeza básica
        df.columns = df.columns.str.strip()
        
        # Conversão de Datas
        if 'Data Primeira Consulta' in df.columns:
            df['Data Primeira Consulta'] = pd.to_datetime(df['Data Primeira Consulta'], errors='coerce')
        if 'Idade' in df.columns:
            df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')

        # --- PROCESSAMENTO DOS DADOS ---
        
        # 1. Coluna de Tempo de Tratamento (Anos)
        if 'Data Primeira Consulta' in df.columns:
            df['Tempo_Anos'] = df['Data Primeira Consulta'].apply(calculate_treatment_time)
        else:
            df['Tempo_Anos'] = np.nan

        # 2. Coluna de Estadiamento Limpo
        col_estagio = [c for c in df.columns if 'Estadiamento' in c]
        if col_estagio:
            df['Estagio_Limpo'] = df[col_estagio[0]].apply(clean_stage)
        else:
            df['Estagio_Limpo'] = None

        # 3. Flags de Óbito e Recidiva (Busca por texto)
        # Palavras-chave para busca
        df['Flag_Obito'] = df.apply(lambda x: check_keyword(x, ['óbito', 'falecimento', 'morte', 'falecido']), axis=1)
        df['Flag_Recidiva'] = df.apply(lambda x: check_keyword(x, ['recidiva', 'retorno da doença']), axis=1)

        # --- GERAÇÃO DA TABELA RESUMO ---
        
        def generate_row(sub_df, label):
            # Contagens Básicas
            total = len(sub_df)
            
            # Idade
            idade_ate_20 = len(sub_df[sub_df['Idade'] <= 20])
            idade_21_40  = len(sub_df[(sub_df['Idade'] > 20) & (sub_df['Idade'] <= 40)])
            idade_41_60  = len(sub_df[(sub_df['Idade'] > 40) & (sub_df['Idade'] <= 60)])
            idade_61_80  = len(sub_df[(sub_df['Idade'] > 60) & (sub_df['Idade'] <= 80)])
            idade_acima_80 = len(sub_df[sub_df['Idade'] > 80])
            
            # Tempo Tratamento
            tempo_ate_2 = len(sub_df[sub_df['Tempo_Anos'] <= 2])
            tempo_3_5   = len(sub_df[(sub_df['Tempo_Anos'] >= 3) & (sub_df['Tempo_Anos'] <= 5)])
            tempo_6_10  = len(sub_df[(sub_df['Tempo_Anos'] >= 6) & (sub_df['Tempo_Anos'] <= 10)])
            tempo_mais_10 = len(sub_df[sub_df['Tempo_Anos'] > 10])
            
            # Estadiamento
            est_I   = len(sub_df[sub_df['Estagio_Limpo'] == 'I'])
            est_II  = len(sub_df[sub_df['Estagio_Limpo'] == 'II'])
            est_III = len(sub_df[sub_df['Estagio_Limpo'] == 'III'])
            est_IV  = len(sub_df[sub_df['Estagio_Limpo'] == 'IV'])
            
            # Óbito e Recidiva
            obitos = sub_df['Flag_Obito'].sum()
            recidivas = sub_df['Flag_Recidiva'].sum()
            
            return {
                'Gênero': label,
                'Linfomas (Total)': total,
                'Idade (≤20)': idade_ate_20,
                'Idade (21-40)': idade_21_40,
                'Idade (41-60)': idade_41_60,
                'Idade (61-80)': idade_61_80,
                'Idade (>80)': idade_acima_80,
                'Tempo (≤2 anos)': tempo_ate_2,
                'Tempo (3-5 anos)': tempo_3_5,
                'Tempo (6-10 anos)': tempo_6_10,
                'Tempo (>10 anos)': tempo_mais_10,
                'Estágio I': est_I,
                'Estágio II': est_II,
                'Estágio III': est_III,
                'Estágio IV': est_IV,
                'Óbitos': obitos,
                'Recidivas (Geral)': recidivas
            }

        # Separar por Gênero
        if 'GENERO' in df.columns:
            df_f = df[df['GENERO'] == 'F']
            df_m = df[df['GENERO'] == 'M']
        else:
            df_f = pd.DataFrame()
            df_m = pd.DataFrame()

        # Criar as linhas
        rows = []
        rows.append(generate_row(df_f, 'Feminino (F)'))
        rows.append(generate_row(df_m, 'Masculino (M)'))
        rows.append(generate_row(df, 'TOTAL'))

        # Criar DataFrame Final
        resumo_df = pd.DataFrame(rows)
        resumo_df.set_index('Gênero', inplace=True)

        # --- EXIBIÇÃO ---
        st.subheader("Tabela de Dados Consolidados")
        st.info("Nota: Óbitos e Recidivas são contados buscando palavras-chave ('óbito', 'recidiva') em todas as colunas de texto.")
        
        # Exibe a tabela
        st.dataframe(resumo_df, use_container_width=True)
        
        # Botão de Download
        csv = resumo_df.to_csv().encode('utf-8')
        st.download_button(
            label="💾 Baixar Tabela como CSV",
            data=csv,
            file_name='resumo_oncologico.csv',
            mime='text/csv',
        )
        
        # Mostrar dados brutos filtrados para conferência (opcional)
        with st.expander("Verificar quais pacientes foram marcados como 'Recidiva'"):
            st.dataframe(df[df['Flag_Recidiva']][['Nome', 'GENERO', 'Diagnóstico Histológico AP', 'Intenção da terapia sistêmica']])

    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
else:
    st.info("Aguardando upload do arquivo.")
