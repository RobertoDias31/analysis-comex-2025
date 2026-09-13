import streamlit as st
import pandas as pd
import sqlalchemy
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Comex Stat - Importações", layout="wide")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "database.db"

ALTURA_GRAFICO = 360
ALTURA_GRAFICO_GRANDE = 440


@st.cache_resource
def get_engine():
    return sqlalchemy.create_engine(f"sqlite:///{DB_PATH}")

engine = get_engine()


def escapar_lista(valores):
    escapados = [v.replace("'", "''") for v in valores]
    return ",".join(f"'{v}'" for v in escapados)


def formatar_numero(valor, decimais=0):
    texto = f"{valor:,.{decimais}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def com_peso_valido(filtro):
    condicao = "flag_peso_zerado = 0"
    return f"{filtro} AND {condicao}" if filtro else f" WHERE {condicao}"


@st.cache_data
def carregar_categorias_n1():
    query = """
        SELECT DISTINCT NO_CGCE_N1
        FROM imp_tratada
        WHERE NO_CGCE_N1 IS NOT NULL
        ORDER BY NO_CGCE_N1
    """
    return pd.read_sql(query, engine)["NO_CGCE_N1"].tolist()

@st.cache_data
def carregar_paises_disponiveis():
    query = "SELECT DISTINCT NO_PAIS FROM imp_tratada WHERE NO_PAIS IS NOT NULL ORDER BY NO_PAIS"
    return pd.read_sql(query, engine)["NO_PAIS"].tolist()


st.title("Análise de Custos Logísticos de Importação")

st.caption("Dados retirados do Comex Stat (MDIC) — importações brasileiras de 2025")

col_categoria, col_fob = st.columns([3, 1])

with col_categoria:
    categorias_disponiveis = carregar_categorias_n1()
    categorias_selecionadas = st.multiselect(
        "Categoria de Produto", options=categorias_disponiveis
    )

with col_fob:
    st.write("")
    excluir_fob_zerado = st.checkbox("Excluir FOB zerado", value=True)

st.divider()


def montar_filtro(alias="imp_tratada"):
    condicoes = []
    if categorias_selecionadas:
        categorias_str = escapar_lista(categorias_selecionadas)
        condicoes.append(f"{alias}.NO_CGCE_N1 IN ({categorias_str})")
    if excluir_fob_zerado:
        condicoes.append(f"{alias}.flag_fob_zerado = 0")
    return " WHERE " + " AND ".join(condicoes) if condicoes else ""

filtro_sql = montar_filtro()


@st.cache_data
def calcular_kpis(filtro):
    query = f"""
        SELECT
            SUM(VL_FOB) AS total_fob,
            SUM(VL_FRETE) AS total_frete
        FROM imp_tratada
        {filtro}
    """
    return pd.read_sql(query, engine).iloc[0]

@st.cache_data
def evolucao_mensal(filtro):
    query = f"""
        SELECT CO_ANO AS ano, CO_MES AS mes, SUM(VL_FOB) AS valor_fob, SUM(VL_FRETE) AS valor_frete
        FROM imp_tratada
        {filtro}
        GROUP BY CO_ANO, CO_MES
        ORDER BY CO_ANO, CO_MES
    """
    df = pd.read_sql(query, engine)
    df["periodo"] = df["ano"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2)
    return df

@st.cache_data
def fob_por_categoria(filtro, coluna_categoria):
    query = f"""
        SELECT {coluna_categoria} AS categoria, SUM(VL_FOB) AS valor_fob
        FROM imp_tratada
        {filtro}
        GROUP BY {coluna_categoria}
        ORDER BY valor_fob DESC
        LIMIT 10
    """
    return pd.read_sql(query, engine)

@st.cache_data
def custo_kg_por_pais(filtro_peso_valido):
    query = f"""
        SELECT pais, frete_por_kg
        FROM (
            SELECT
                NO_PAIS AS pais,
                SUM(VL_FOB) AS fob_total,
                ROUND(SUM(VL_FRETE) * 1.0 / NULLIF(SUM(KG_LIQUIDO), 0), 4) AS frete_por_kg
            FROM imp_tratada
            {filtro_peso_valido}
            GROUP BY NO_PAIS
            ORDER BY fob_total DESC
            LIMIT 30
        )
        WHERE frete_por_kg IS NOT NULL
        ORDER BY frete_por_kg DESC
        LIMIT 10
    """
    return pd.read_sql(query, engine)

@st.cache_data
def ranking_por_pais(filtro):
    query = f"""
        SELECT
            NO_PAIS AS pais,
            SUM(VL_FOB) AS valor_fob,
            SUM(VL_FRETE) AS frete_total,
            COUNT(*) AS registros
        FROM imp_tratada
        {filtro}
        GROUP BY NO_PAIS
    """
    return pd.read_sql(query, engine)

@st.cache_data
def valor_por_bloco(filtro_alias_i):
    query = f"""
        SELECT b.NO_BLOCO AS bloco, SUM(i.VL_FOB) AS valor_fob
        FROM imp_tratada AS i
        JOIN tb_pais_bloco AS b ON i.CO_PAIS = b.CO_PAIS
        {filtro_alias_i}
        GROUP BY b.NO_BLOCO
        ORDER BY valor_fob DESC
        LIMIT 10
    """
    return pd.read_sql(query, engine)

@st.cache_data
def registros_por_estado(filtro):
    query = f"""
        SELECT SG_UF_NCM AS estado, COUNT(*) AS registros
        FROM imp_tratada
        {filtro}
        GROUP BY SG_UF_NCM
        ORDER BY registros DESC
    """
    return pd.read_sql(query, engine)

@st.cache_data
def top10_urf(filtro):
    query = f"""
        SELECT NO_URF AS local_entrada, COUNT(*) AS registros
        FROM imp_tratada
        {filtro}
        GROUP BY NO_URF
        ORDER BY registros DESC
        LIMIT 10
    """
    return pd.read_sql(query, engine)

@st.cache_data
def modal_transporte(filtro, pais_filtro):
    filtro_extra = ""
    if pais_filtro != "Todos":
        pais_escapado = pais_filtro.replace("'", "''")
        clausula_pais = f"NO_PAIS = '{pais_escapado}'"
        filtro_extra = f" WHERE {clausula_pais}" if filtro == "" else f" AND {clausula_pais}"

    query = f"""
        SELECT NO_VIA AS modal, SUM(VL_FOB) AS valor_fob
        FROM imp_tratada
        {filtro}{filtro_extra}
        GROUP BY NO_VIA
        ORDER BY valor_fob DESC
    """
    return pd.read_sql(query, engine)


kpis = calcular_kpis(filtro_sql)

col_kpi1, col_kpi2 = st.columns(2)
with col_kpi1:
    st.metric("Valor FOB Total", f"USD {formatar_numero(kpis['total_fob'])}")
with col_kpi2:
    st.metric("Frete Total", f"USD {formatar_numero(kpis['total_frete'])}")

st.divider()


st.subheader("Evolução mensal: FOB e frete")

df_evolucao = evolucao_mensal(filtro_sql)

fig_evolucao = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1)
fig_evolucao.add_trace(
    go.Scatter(x=df_evolucao["periodo"], y=df_evolucao["valor_fob"],
               name="FOB", mode="lines+markers"),
    row=1, col=1
)
fig_evolucao.add_trace(
    go.Scatter(x=df_evolucao["periodo"], y=df_evolucao["valor_frete"],
               name="Frete", mode="lines+markers"),
    row=2, col=1
)
fig_evolucao.update_yaxes(title_text="FOB (USD)", automargin=True, row=1, col=1)
fig_evolucao.update_yaxes(title_text="Frete (USD)", automargin=True, row=2, col=1)
fig_evolucao.update_xaxes(title_text="Mês", automargin=True, row=2, col=1)
fig_evolucao.update_layout(
    separators=",.", height=ALTURA_GRAFICO, margin=dict(t=20, b=20),
    legend=dict(orientation="h", y=1.12)
)
st.plotly_chart(fig_evolucao, width='stretch')


st.subheader("Valor importado por categoria de produto")

nivel_cgce = st.radio(
    "Nível de detalhe:", options=["Visão Geral", "Intermediário", "Detalhado"],
    horizontal=True, key="radio_cgce"
)

mapa_colunas = {
    "Visão Geral": "NO_CGCE_N1",
    "Intermediário": "NO_CGCE_N2",
    "Detalhado": "NO_CGCE_N3",
}

df_categoria = fob_por_categoria(filtro_sql, mapa_colunas[nivel_cgce])

fig_categoria = px.bar(
    df_categoria.sort_values("valor_fob"),
    x="valor_fob", y="categoria", orientation="h",
    labels={"valor_fob": "Valor FOB (USD)", "categoria": ""}
)
fig_categoria.update_layout(
    separators=",.", height=ALTURA_GRAFICO_GRANDE, margin=dict(t=20, b=20, l=20, r=20),
    yaxis=dict(automargin=True), xaxis=dict(automargin=True)
)
st.plotly_chart(fig_categoria, width='stretch')


col_titulo_kg, col_titulo_ranking = st.columns(2)
with col_titulo_kg:
    st.subheader("Custo de frete/kg por país")
with col_titulo_ranking:
    st.subheader("Ranking por país (Top 10)")

col_controle_kg, col_controle_ranking = st.columns(2)
with col_controle_kg:
    modal_kg = st.radio(
        "Modal de transporte:", options=["Sem modal aéreo", "Somente modal aéreo"],
        horizontal=True, key="radio_modal_kg"
    )
with col_controle_ranking:
    metrica_pais = st.radio(
        "Métrica:", options=["Valor FOB", "Frete Total", "Registros"],
        horizontal=True, key="radio_ranking_pais"
    )

mapa_modal_kg = {
    "Sem modal aéreo": ("CO_VIA <> 4", "Todos os modais, exceto o aéreo", "sem aéreo"),
    "Somente modal aéreo": ("CO_VIA = 4", "Somente o modal aéreo", "somente aéreo"),
}
condicao_modal_kg, titulo_modal_kg, sufixo_modal_kg = mapa_modal_kg[modal_kg]

mapa_metrica_pais = {
    "Valor FOB": ("valor_fob", "Valor FOB (USD)"),
    "Frete Total": ("frete_total", "Frete Total (USD)"),
    "Registros": ("registros", "Registros"),
}
coluna_metrica, rotulo_metrica = mapa_metrica_pais[metrica_pais]

df_kg_pais = custo_kg_por_pais(f"{com_peso_valido(filtro_sql)} AND {condicao_modal_kg}")
fig_kg_pais = px.bar(
    df_kg_pais.sort_values("frete_por_kg"),
    x="frete_por_kg", y="pais", orientation="h",
    title=titulo_modal_kg,
    labels={"frete_por_kg": f"Frete/KG (USD) — {sufixo_modal_kg}", "pais": ""}
)
fig_kg_pais.update_layout(
    separators=",.", height=ALTURA_GRAFICO, margin=dict(t=50, b=20),
    yaxis=dict(automargin=True), xaxis=dict(automargin=True)
)

df_pais = ranking_por_pais(filtro_sql).nlargest(10, coluna_metrica)
fig_pais = px.bar(
    df_pais.sort_values(coluna_metrica),
    x=coluna_metrica, y="pais", orientation="h",
    title=rotulo_metrica,
    labels={coluna_metrica: rotulo_metrica, "pais": ""}
)
fig_pais.update_layout(
    separators=",.", height=ALTURA_GRAFICO, margin=dict(t=50, b=20),
    yaxis=dict(automargin=True), xaxis=dict(automargin=True)
)

col_grafico_kg, col_grafico_ranking = st.columns(2)
with col_grafico_kg:
    st.plotly_chart(fig_kg_pais, width='stretch')
with col_grafico_ranking:
    st.plotly_chart(fig_pais, width='stretch')


col_titulo_modal, col_titulo_bloco = st.columns(2)
with col_titulo_modal:
    st.subheader("Modal de transporte (valor FOB)")
with col_titulo_bloco:
    st.subheader("Valor importado por bloco econômico")

col_controle_modal, _ = st.columns(2)
with col_controle_modal:
    paises_disponiveis = carregar_paises_disponiveis()
    pais_selecionado = st.selectbox(
        "Filtrar por país (opcional):", options=["Todos"] + paises_disponiveis,
        key="select_pais_modal"
    )

df_modal = modal_transporte(filtro_sql, pais_selecionado)
fig_modal = px.pie(
    df_modal, names="modal", values="valor_fob", hole=0.55,
    labels={"modal": "Modal", "valor_fob": "Valor FOB (USD)"}
)
fig_modal.update_traces(textinfo="percent", textposition="inside", sort=True)
fig_modal.update_layout(
    separators=",.", height=ALTURA_GRAFICO, margin=dict(t=20, b=20),
    legend=dict(orientation="v", x=1, y=0.5)
)

df_bloco = valor_por_bloco(montar_filtro(alias="i"))
fig_bloco = px.bar(
    df_bloco.sort_values("valor_fob"),
    x="valor_fob", y="bloco", orientation="h",
    labels={"valor_fob": "Valor FOB (USD)", "bloco": ""}
)
fig_bloco.update_layout(
    separators=",.", height=ALTURA_GRAFICO, margin=dict(t=20, b=20),
    yaxis=dict(automargin=True), xaxis=dict(automargin=True)
)

col_grafico_modal, col_grafico_bloco = st.columns(2)
with col_grafico_modal:
    st.plotly_chart(fig_modal, width='stretch')
with col_grafico_bloco:
    st.plotly_chart(fig_bloco, width='stretch')


st.subheader("Registros por estado / local de entrada")

visao_local = st.radio(
    "Visualizar por:", options=["Estado (Top 10)", "Local de entrada (Top 10)"],
    horizontal=True, key="radio_local"
)

if visao_local == "Estado (Top 10)":
    df_local = registros_por_estado(filtro_sql).nlargest(10, "registros")
    fig_local = px.bar(
        df_local.sort_values("registros"),
        x="registros", y="estado", orientation="h",
        labels={"registros": "Registros", "estado": ""}
    )
else:
    df_local = top10_urf(filtro_sql)
    fig_local = px.bar(
        df_local.sort_values("registros"),
        x="registros", y="local_entrada", orientation="h",
        labels={"registros": "Registros", "local_entrada": ""}
    )

fig_local.update_layout(
    separators=",.", height=ALTURA_GRAFICO, margin=dict(t=20, b=20),
    yaxis=dict(automargin=True), xaxis=dict(automargin=True)
)
st.plotly_chart(fig_local, width='stretch')
