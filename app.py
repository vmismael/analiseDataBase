import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Relatório de Pacientes", layout="wide")
st.title("📋 Relatório Consolidado - Dados Oncológicos")

# --- ESTILO CSS PARA TABELA COMPACTA ---
st.markdown("""
<style>
    .dataframe {font-size: 12px !important;}
    table {width: 100%;}
    th, td {text-align: center !important; padding: 8px !important;}
    th {background-color: #f0f2f6;}
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LIMPEZA E CÁLCULO ---

def clean_stage(val):
    """Extrai I, II, III, IV do texto do estadiamento"""
    if pd.isna(val): return None
    s = str(val).upper()
    # Procura algarismos romanos isolados
    match = re.search(r'\b(IV|III|II|I)\b', s)
    return match.group(1) if match else None

def get_year_from_date(val):
    """Extrai ano de uma data"""
    try:
        if pd.isna(val): return None
        return pd.to_datetime(val).year
    except:
        return None

def calculate_time_years(row):
    """
    Calcula tempo de tratamento em anos.
    Se Óbito: Data Óbito - Data 1ª Consulta
    Se Vivo:  2024-12-31 - Data 1ª Consulta
    """
    try:
        start_date = row['Data Primeira Consulta']
        obito_date = row['Data_Obito_Valida'] # Coluna auxiliar criada depois
        
        if pd.isna(start_date): return None
        
        end_date = pd.Timestamp("2024-12-31")
        if pd.notna(obito_date):
            end_date = obito_date
            
        if start_date > end_date: return 0
        
        return (end_date - start_date).days / 365.25
    except:
        return None

# --- CARREGAMENTO DO ARQUIVO ---
st.sidebar.header("📁 Importar Arquivo")
uploaded_file = st.sidebar.file_uploader("Selecione o arquivo CSV ou Excel", type=["csv", "xlsx"])

# Opção manual caso a detecção automática falhe
header_row = st.sidebar.number_input("Linha do Cabeçalho (0-based)", value=7, min_value=0, help="Geralmente é 7 para este modelo de arquivo.")

if uploaded_file:
    try:
        # 1. Leitura do Arquivo
        if uploaded_file.name.lower().endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, header=header_row)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, header=header_row, sep=';', encoding='latin1')
        else:
            df = pd.read_excel(uploaded_file, header=header_row)

        # 2. Normalização de Colunas (strip espaços)
        df.columns = df.columns.str.strip()
        
        # Verificar se colunas essenciais existem
        required_cols = ['GENERO', 'Data Primeira Consulta']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Colunas não encontradas. Verifique a linha do cabeçalho. Colunas lidas: {list(df.columns)}")
        else:
            # --- PROCESSAMENTO ---
            
            # Converter Datas
            df['Data Primeira Consulta'] = pd.to_datetime(df['Data Primeira Consulta'], errors='coerce')
            df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')
            
            # Tratamento da Coluna Óbito (que contém datas ou NaN) e Recidiva
            # Mapeando nomes prováveis das colunas baseadas no arquivo novo
            col_obito = [c for c in df.columns if 'Óbito' in c][0]
            col_recidiva_flag = [c for c in df.columns if 'Recidiva (S) ou (N)' in c][0]
            col_recidiva_data = [c for c in df.columns if 'Data de Inicio do tratamento pós recidiva' in c]
            
            # Converter coluna de Óbito para data real (para quem morreu)
            df['Data_Obito_Valida'] = pd.to_datetime(df[col_obito], errors='coerce')
            # Flag booleana de óbito (se tem data, morreu)
            df['Is_Obito'] = df['Data_Obito_Valida'].notna()
            
            # Flag de Recidiva
            df['Is_Recidiva'] = df[col_recidiva_flag].astype(str).str.strip().str.upper() == 'S'
            
            # Ano da Recidiva (para as colunas 202X)
            if col_recidiva_data:
                df['Ano_Recidiva'] = pd.to_datetime(df[col_recidiva_data[0]], errors='coerce').dt.year
            else:
                df['Ano_Recidiva'] = np.nan

            # Tempo de Tratamento
            df['Tempo_Anos'] = df.apply(calculate_time_years, axis=1)
            
            # Estadiamento Limpo
            col_estagio = [c for c in df.columns if 'Estadiamento' in c][0]
            df['Estagio_Limpo'] = df[col_estagio].apply(clean_stage)

            # --- GERAÇÃO DA TABELA ---
            
            def create_summary_row(sub_df, label):
                # Totais
                total = len(sub_df)
                
                # Faixas Etárias
                age_bins = [0, 20, 40, 60, 80, 150]
                age_labels = ['≤20', '21-40', '41-60', '61-80', '>80']
                # cut divide em faixas, value_counts conta
                if not sub_df.empty and sub_df['Idade'].notna().any():
                    age_counts = pd.cut(sub_df['Idade'], bins=age_bins, labels=age_labels, right=True).value_counts()
                else:
                    age_counts = pd.Series(0, index=age_labels)

                # Faixas Tempo Tratamento
                time_bins = [-1, 2, 5, 10, 100] # -1 a 2, 2 a 5, 5 a 10...
                time_labels = ['≤2 anos', '3-5 anos', '6-10 anos', '>10 Anos']
                if not sub_df.empty and sub_df['Tempo_Anos'].notna().any():
                    time_counts = pd.cut(sub_df['Tempo_Anos'], bins=time_bins, labels=time_labels).value_counts()
                else:
                    time_counts = pd.Series(0, index=time_labels)

                # Estadiamento
                est_I   = len(sub_df[sub_df['Estagio_Limpo'] == 'I'])
                est_II  = len(sub_df[sub_df['Estagio_Limpo'] == 'II'])
                est_III = len(sub_df[sub_df['Estagio_Limpo'] == 'III'])
                est_IV  = len(sub_df[sub_df['Estagio_Limpo'] == 'IV'])

                # Óbitos
                obitos = sub_df['Is_Obito'].sum()
                
                # Recidivas (Geral e por Ano Recente)
                recidivas_total = sub_df['Is_Recidiva'].sum()
                
                # Montar Dicionário da Linha
                data = {
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
                    
                    # Estadiamento
                    'Est. I': est_I,
                    'Est. II': est_II,
                    'Est. III': est_III,
                    'Est. IV': est_IV,
                    
                    'Óbitos': obitos,
                    # 'Recidivas (Total)': recidivas_total # Opcional, se quiser o total geral
                }
                
                # Adicionar colunas dinâmicas de Recidiva por Ano (ex: Recidiva 2022)
                # Vamos pegar os anos presentes no dataset geral para manter consistência das colunas
                anos_relevantes = sorted(df['Ano_Recidiva'].dropna().unique())
                for ano in anos_relevantes:
                    ano_int = int(ano)
                    qtd_ano = len(sub_df[sub_df['Ano_Recidiva'] == ano])
                    data[f'{ano_int} (Recidiva)'] = qtd_ano
                
                # Se não houver anos detectados, coloca uma coluna genérica
                if not anos_relevantes:
                    data['Recidivas (Total)'] = recidivas_total
                
                return data

            # Separar grupos
            rows = []
            rows.append(create_summary_row(df[df['GENERO'] == 'F'], 'F'))
            rows.append(create_summary_row(df[df['GENERO'] == 'M'], 'M'))
            rows.append(create_summary_row(df, 'Total'))
            
            # Criar DataFrame Final
            resumo_df = pd.DataFrame(rows).set_index('Gênero')
            
            # Transpor se necessário (mas o pedido foi Linhas F/M/Total, então mantemos assim)
            
            # EXIBIR
            st.write("### Tabela Consolidada")
            st.dataframe(resumo_df, use_container_width=True)
            
            # Download
            csv = resumo_df.to_csv().encode('utf-8')
            st.download_button("💾 Baixar Tabela CSV", csv, "resumo_oncologico_v2.csv", "text/csv")
            
            # --- DEBUG (OPCIONAL - REMOVA SE NÃO QUISER VER) ---
            with st.expander("Verificar detecção de Óbitos e Recidivas"):
                st.write("Pacientes detectados como Óbito (Coluna tem Data):")
                st.dataframe(df[df['Is_Obito']][['Nome', 'GENERO', col_obito]])
                
                st.write("Pacientes detectados como Recidiva (Flag = S):")
                st.dataframe(df[df['Is_Recidiva']][['Nome', 'GENERO', col_recidiva_flag, 'Ano_Recidiva']])

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        st.info("Dica: Verifique se o arquivo não está corrompido e se a linha do cabeçalho (7) está correta.")

else:
    st.info("Aguardando arquivo...")
