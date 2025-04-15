import streamlit as st

st.set_page_config(page_title="Phoning report", page_icon=":bar_chart:", layout="wide")

def set_custom_css():
    st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        :root {
            --main-bg: #e6e9ef;
            --sidebar-bg: #2c3e50;
            --primary: #2980b9;
            --primary-hover: #3498db;
            --text-white: white;
            --header-color: #2c3e50;
        }
        div[data-testid="stMarkdownContainer"] {
    color: var(--text-white);
        }
        section.main > div {
            color: black;
        }
        section[data-testid="stSidebar"] {
            background-color: var(--sidebar-bg);
            color: var(--text-white);
        }
        section[data-testid="stSidebar"] * {
            color: var(--text-white) !important;
        }
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3 {
            color: var(--header-color);
        }
        .stButton>button {
            background-color: var(--primary);
            color: var(--text-white);
            border-radius: 6px;
            padding: 0.4em 1em;
            border: none;
        }
        .stButton>button:hover {
            background-color: var(--primary-hover);
            color: var(--text-white);
        }
        .stApp {
            background-color: #f7f9fc;
        }

        /* CORRECTION TEXTE INVISIBLE */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {
            color: black !important;
            background-color: white !important;
        }
        input, textarea {
            color: black !important;
        }
    </style>
    """, unsafe_allow_html=True)

set_custom_css()

from streamlit import sidebar, session_state
import pandas as pd
import re
from io import BytesIO
import time
import openpyxl

TIMEOUT_DURATION = 15 * 60  # 15 minutes

if "last_active" not in st.session_state:
    st.session_state["last_active"] = time.time()

if time.time() - st.session_state["last_active"] > TIMEOUT_DURATION:
    st.warning("Session expirée pour inactivité. Veuillez vous reconnecter.")
    if st.button("Se reconnecter"):
        st.session_state["auth"] = False
        st.query_params.clear()
        st.rerun()
    st.stop()

# Fonction pour mettre en forme le tableau généré
def style_dataframe(df):
    for col in df.select_dtypes(include='number').columns:
        df[col] = df[col].astype(int)

    styled = df.style.set_table_styles([
        {
            "selector": "thead, th",
            "props": [
                ("background-color", "#2c3e50"),
                ("color", "white"),
                ("font-weight", "bold"),
                ("text-align", "center"),
                ("border", "2px solid #000030")
            ]
        }
    ]).apply(lambda x: ['background-color: #f2f2f2' if i % 2 == 0 else
                        'background-color: #ffffff' for i in range(len(x))],
             axis=0)
    for col in df.select_dtypes(include='number').columns:
        styled = styled.format({col: '{:.0f}'.format})
    return styled

# Fonction pour extraire le numéro de téléphone de la colonne LOG
def extract(text: str) -> str | None:
    pattern = r'\b229\d{10}\b'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0]
    return None

# Fonction pour formater un nombre avec séparateur de millier
def format_number(n):
    return f'{n:,}'.replace(',', ' ')

# Fonction pour exporter le reporting en fichier Excel
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()
# Fonction de connexion

def check_credentials():
    st.sidebar.header("Connexion")
    username = st.sidebar.text_input("Nom d'utilisateur")
    password = st.sidebar.text_input("Mot de passe", type="password")
    if sidebar.button("Se connecter"):
        if username == USERNAME and password == PASSWORD:
            st.success("Connecté")
            st.session_state["auth"] = True
            st.query_params.update({"auth": "yes"})
            st.rerun()
        else:
            st.sidebar.error("Nom d'utilisateur ou mot de passe invalides")
    st.stop()

# Fonction principale
def mm_report(deb, rp):
    # Conversion des noms de colonnes en majuscules
    rp.columns = [colname.upper() for colname in list(rp.columns)]
    deb.columns = [colname.upper() for colname in list(deb.columns)]
    rp = rp[rp['USERNAME'].str.contains('WEBC_|webc_')]
    deb = deb[deb['USERNAME'].str.contains('WEBC_|webc_')]

    # Extraction des numéros de téléphone
    for df in [deb, rp]:
        df['MSISDN'] = df['LOG'].map(extract)

    # Extraction du motif de blocage
    deb['LOCK DESCRIPTION'] = deb['LOG'].map(lambda x: x.split(': ')[-1])

    # Caractérisation du statut de l'opération (unlock) en fonction du motif de blocage
    option = {'INVALID PASSWORD': 'REUSSI', 'FAILED TRANSACTION': 'REUSSI', '': 'ECHOUE'}
    deb['NIVEAU_1'] = deb['LOCK DESCRIPTION'].map(lambda x: option[x] if x in option.keys() else 'NON AUTORISE')
    rp['NIVEAU_1'] = rp['LOG'].map(lambda x: 'REUSSI' if x.find('uccessfully') > 0 else 'ECHOUE')

    # Requalification des actions "non autorisées" en "actions autorisées" pour Yanelle
    yanelle_idx = deb[(deb['NIVEAU_1'] == 'NON AUTORISE') & (deb['USERNAME'] == 'CC_DOPEME_WEBC_EANNE')].index
    deb.loc[yanelle_idx, 'NIVEAU_1'] = 'REUSSI'
    rp = rp[rp['NIVEAU_1'] == 'REUSSI']
    unauth = deb[deb['NIVEAU_1'] == 'NON AUTORISE'].copy()
    deb = deb[deb['NIVEAU_1'] == 'REUSSI']
    group_deb = deb.groupby('USERNAME').size().reset_index(name='UNLOCK')
    group_unauth = unauth.groupby('USERNAME').size().reset_index(name='UNAUTH')
    reset = rp[~rp['MSISDN'].isin(deb['MSISDN'])]
    group_reset = reset.groupby('USERNAME').size().reset_index(name='RESET_ONLY')
    group_deb = group_deb.merge(group_reset, how='left', on='USERNAME')
    group_deb = group_deb.merge(group_unauth, how='left', on='USERNAME').fillna(0)
    group_deb = group_deb.assign(TOTAL=group_deb['UNLOCK'] + group_deb['RESET_ONLY'])
    group_deb = group_deb.sort_values(by='TOTAL', ascending=False)
    group_deb.index = range(1, len(group_deb) + 1)
    rp_agent = rp[rp['MODULE'] != 'RESET MOBILE PASSWORD']
    group_agent = rp_agent.pivot_table(index='USERNAME', columns='MODULE', aggfunc='size', fill_value=0)
    group_agent = group_agent.reset_index()
    group_agent.index.name = None
    group_agent = group_agent.sort_values(by='APPROVE RESET PIN', ascending=False)
    group_agent = group_agent[['USERNAME', 'APPROVE RESET PIN', 'REJECT RESET PIN', 'LOCK ACCOUNT']]
    group_agent.index = range(1, len(group_agent) + 1)
    return group_deb, group_agent

# --------------------------------------
# 1. Authentification
# --------------------------------------
# Chargement des identifiants de connexion
USERNAME = st.secrets["auth"]["APP_USERNAME"]
PASSWORD = st.secrets["auth"]["APP_PASSWORD"]

# Vérification des paramètres dans l'URL
if st.query_params.get("auth") == "yes":
    st.session_state.auth = True
    st.session_state["last_active"] = time.time()

# Initialisation de l'état de session
if "auth" not in st.session_state:
    st.session_state["auth"] = False

# Tentative de connexion/ déconnexion si utilisateur déjà connecté
if not session_state["auth"]:
    check_credentials()
    st.stop()
else:
    st.sidebar.markdown("---")
    if st.sidebar.button("Se déconnecter"):
        st.session_state["auth"] = False
        st.query_params.clear()
        st.rerun()
# --------------------------------------
# 2. Upload du fichier
# --------------------------------------
st.title("PHONING REPORT")

uploaded_file = st.file_uploader("Joindre le fichier Excel", type=["xlsx"])

if uploaded_file:
    df_1 = pd.read_excel(uploaded_file, sheet_name='unlock', parse_dates=['Timestamp'])
    df_2 = pd.read_excel(uploaded_file, sheet_name='reset_pin', parse_dates=['Timestamp'])
    st.session_state["last_active"] = time.time()
    # --------------------------------------
    # Sélection de la période de reporting
    # --------------------------------------
    min_date = min(df_1['Timestamp'].min(), df_2['Timestamp'].min()).date()
    max_date = max(df_1['Timestamp'].max(), df_2['Timestamp'].max()).date()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 Date de début", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("📅 Date de fin", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("⚠ La date de début doit être antérieure ou égale à la date de fin.")
    else:
        # Filtrage des données selon les dates choisies
        mask_1 = df_1["Timestamp"].dt.date.between(start_date, end_date)
        mask_2 = df_2["Timestamp"].dt.date.between(start_date, end_date)
        df_1 = df_1[mask_1]
        df_2 = df_2[mask_2]
    # --------------------------------------
    # 3. Appel de la fonction de reporting
    # --------------------------------------
    reporting_type = st.selectbox("Choisir le reporting à afficher :",
                                  ["Déblocage", "Réinitialisation Agent"])
    if reporting_type:
        st.session_state["last_active"] = time.time()

    if st.button("Générer le rapport"):
        deb_report, agent_report = mm_report(df_1, df_2)
        left_col, right_col = st.columns([3, 1])
        if reporting_type == "Déblocage":
            left_col.subheader("Point des déblocages")
            # left_col.dataframe(style_dataframe(deb_report),
            #                    hide_index=True, use_container_width=True)
            left_col.write(style_dataframe(deb_report).to_html(),
                               unsafe_allow_html=True)
            right_col.markdown(f"""
            # 
            ##### ☑ Débloqué : {format_number(deb_report['UNLOCK'].sum())}
            ##### ☑ Réinitialisé : {format_number(deb_report['RESET_ONLY'].sum())}
            ##### ☑ Total : {format_number(deb_report['TOTAL'].sum()):,}
            """, unsafe_allow_html=True)
            to_export = deb_report
        else:
            left_col.subheader("Point des reset pin Agent")
            # left_col.write(style_dataframe(agent_report),
            #                    hide_index=True, use_container_width=True)
            left_col.write(style_dataframe(agent_report).to_html(),
                               unsafe_allow_html=True)
            right_col.markdown(f"""
            # 
            ##### ☑ Approuvé : {format_number(agent_report['APPROVE RESET PIN'].sum())}
            ##### ☑ Rejeté : {format_number(agent_report['REJECT RESET PIN'].sum())}
            ##### ☑ Total : {format_number(agent_report[['APPROVE RESET PIN', 'REJECT RESET PIN']].apply(sum, axis=1)
                              .sum())}
            """, unsafe_allow_html=True)
            to_export = agent_report
            st.session_state["last_active"] = time.time()

    # Exportation
        if not to_export.empty:
            st.download_button(label="Exporter en Excel", data=convert_df_to_excel(to_export),
                               file_name = f"{reporting_type.lower().replace(' ', '_')}.xlsx",
                               mime = "application/vnd.openxmlformats-officedocument.spreadsheet.sheet")
            st.session_state["last_active"] = time.time()
        else:
            st.warning("Aucune donnée à exporter.")
            st.session_state["last_active"] = time.time()

