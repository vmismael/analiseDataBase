import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página
st.set_page_config(page_title="Dashboard Oncológico", layout="wide")

# Título
st.title("📊 Análise de Dados - Pacientes Oncológicos")

# --- BARRA LATERAL (UPLOAD E FILTROS) ---
st.sidebar.header("Configurações")

# 1. Componente para carregar o arquivo
uploaded_file = st.sidebar.file_uploader("Carregue seu arquivo (CSV ou Excel)", type=["csv", "xlsx"])

# Opção para ajustar quantas linhas pular (caso o cabeçalho mude)
linhas_para_pular = st.sidebar.number_input("Linhas de cabeçalho para pular", min_value=0, value=7, help="Ajuste se o arquivo tiver linhas de metadados antes da tabela real.")

@st.cache_data
def load_data(file, skiprows):
    try:
        # Verifica a extensão do arquivo para usar o leitor correto
        if file.name.endswith('.csv'):
            # Tenta ler CSV (as vezes o separador é ; ou , e o encoding varia)
            try:
                df = pd.read_csv(file, skiprows=skiprows)
            except:
                file.seek(0)
                df = pd.read_csv(file, skiprows=skiprows, sep=';', encoding='latin1')
        else:
            # Lê Excel
            df = pd.read_excel(file, skiprows=skiprows)
        
        # Limpar nomes das colunas (remover espaços extras)
        df.columns = df.columns.str.strip()
        
        # Converter colunas de data
        date_cols = ['Data Primeira Consulta', 'Data de Nascimento', 'Data Diagnóstico   Biópsia']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Garantir que Idade é numérico
        if 'Idade' in df.columns:
            df['Idade'] = pd.to_numeric(df['Idade'], errors='coerce')
            
        return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return pd.DataFrame()

# Lógica Principal: Só roda se houver arquivo
if uploaded_file is not None:
    df = load_data(uploaded_file, linhas_para_pular)

    if not df.empty:
        # --- FILTROS DE DADOS ---
        st.sidebar.subheader("Filtros de Dados")
        
        # Filtro de Gênero
        if 'GENERO' in df.columns:
            generos = df['GENERO'].unique().tolist()
            genero_selecionado = st.sidebar.multiselect("Selecione o Gênero", generos, default=generos)
        else:
            genero_selecionado = []

        # Filtro de Estadiamento
        if 'Estadiamento (is, I, II, III e IV)' in df.columns:
            # Converte para string para evitar erros de tipos mistos
            estagios = df['Estadiamento (is, I, II, III e IV)'].astype(str).unique().tolist()
            estagio_selecionado = st.sidebar.multiselect("Estadiamento", estagios, default=estagios)
        else:
            estagio_selecionado = []

        # Aplicar Filtros
        if 'GENERO' in df.columns and 'Estadiamento (is, I, II, III e IV)' in df.columns:
            df_filtered = df[
                (df['GENERO'].isin(genero_selecionado)) &
                (df['Estadiamento (is, I, II, III e IV)'].astype(str).isin(estagio_selecionado))
            ]
        else:
            df_filtered = df # Se não tiver as colunas, mostra tudo

        # --- KPIs (INDICADORES) ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Pacientes (Filtro)", len(df_filtered))
        
        if 'Idade' in df_filtered.columns:
            media_idade = df_filtered['Idade'].mean()
            col2.metric("Média de Idade", f"{media_idade:.1f} anos")
        
        if 'Data Diagnóstico   Biópsia' in df_filtered.columns:
            ano_min = df_filtered['Data Diagnóstico   Biópsia'].dt.year.min()
            ano_max = df_filtered['Data Diagnóstico   Biópsia'].dt.year.max()
            if pd.notna(ano_min) and pd.notna(ano_max):
                col3.metric("Período dos Diagnósticos", f"{int(ano_min)} - {int(ano_max)}")

        st.markdown("---")

        # --- GRÁFICOS ---
        
        # Linha 1: Gênero e Idade
        c1, c2 = st.columns(2)
        
        with c1:
            if 'GENERO' in df_filtered.columns:
                st.subheader("Distribuição por Gênero")
                fig_gen = px.pie(df_filtered, names='GENERO', title='Pacientes por Gênero', hole=0.4)
                st.plotly_chart(fig_gen, use_container_width=True)
            
        with c2:
            if 'Idade' in df_filtered.columns:
                st.subheader("Distribuição por Idade")
                fig_age = px.histogram(df_filtered, x='Idade', nbins=20, title='Histograma de Idade', color_discrete_sequence=['#3366CC'])
                st.plotly_chart(fig_age, use_container_width=True)

        # Linha 2: Estadiamento e Diagnósticos
        c3, c4 = st.columns(2)
        
        with c3:
            st.subheader("Estadiamento")
            if 'Estadiamento (is, I, II, III e IV)' in df_filtered.columns:
                estagio_counts = df_filtered['Estadiamento (is, I, II, III e IV)'].value_counts().reset_index()
                estagio_counts.columns = ['Estágio', 'Contagem']
                fig_est = px.bar(estagio_counts, x='Estágio', y='Contagem', title='Pacientes por Estadiamento', color='Contagem')
                st.plotly_chart(fig_est, use_container_width=True)
                
        with c4:
            st.subheader("Top 10 Diagnósticos (Histologia)")
            if 'Diagnóstico Histológico AP' in df_filtered.columns:
                diag_counts = df_filtered['Diagnóstico Histológico AP'].value_counts().nlargest(10).reset_index()
                diag_counts.columns = ['Diagnóstico', 'Qtd']
                fig_diag = px.bar(diag_counts, x='Qtd', y='Diagnóstico', orientation='h', title='Diagnósticos Mais Frequentes')
                fig_diag.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_diag, use_container_width=True)

        # Linha 3: Evolução Temporal
        st.subheader("Evolução de Diagnósticos por Ano")
        if 'Data Diagnóstico   Biópsia' in df_filtered.columns:
            df_filtered['Ano Diagnostico'] = df_filtered['Data Diagnóstico   Biópsia'].dt.year
            timeline = df_filtered.groupby('Ano Diagnostico').size().reset_index(name='Pacientes')
            fig_time = px.line(timeline, x='Ano Diagnostico', y='Pacientes', markers=True, title='Novos Casos por Ano')
            st.plotly_chart(fig_time, use_container_width=True)

        # Exibir Tabela
        with st.expander("Ver Dados Brutos"):
            st.dataframe(df_filtered)
    else:
        st.warning("O arquivo carregado não parece conter dados válidos ou as colunas esperadas.")

else:
    # Tela inicial antes de carregar o arquivo
    st.info("👆 Por favor, carregue um arquivo CSV ou Excel na barra lateral para começar.")
