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
        color: black;
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
        /* Customisation des messages d'alerte */
        div[data-testid="stNotification"] {
        color: black !important;
        background-color: #f9e79f !important; /* Jaune pâle */
        border: 1px solid #f1c40f;
        border-radius: 8px;
        padding: 0.75em;
        }
        /* CORRECTION TEXTE INVISIBLE */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {
            color: black !important;
            background-color: white !important;
        }
        input, textarea {
            color: black !important;
            background-color : white;
        }
            /* Correction spécifique pour les DataFrames */
        div[data-testid="stDataFrame"] {
        color: black !important;
        }
        /* Correction pour les tableaux Markdown */
        div[data-testid="stMarkdownContainer"] table {
        color: black !important;
        }
        .stDownloadButton>button {
        background-color: var(--primary) !important;
        color: var(--text-white) !important;
        border-radius: 6px;
        padding: 0.4em 1em;
        border: none;
        }
        /* Correction pour le texte dans la colonne de droite */
        div[data-testid="column"]:last-child div[data-testid="stMarkdownContainer"] {
        color: black !important; /* Cible spécifiquement la colonne de droite */
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

TIMEOUT_DURATION = 60 * 15  # 15 minutes

if "last_active" not in st.session_state:
    st.session_state["last_active"] = time.time()
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if time.time() - st.session_state["last_active"] > TIMEOUT_DURATION:
    st.warning("Session expirée ! Veuillez vous reconnecter.")
    if st.button("Se reconnecter"):
        st.session_state["auth"] = False
        st.query_params.clear()
        st.session_state["last_active"] = time.time()
        st.rerun()
    st.stop()
st.session_state["last_active"] = time.time()

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
    deb['MSISDN'] = deb['LOG'].map(extract)
    rp['MSISDN'] = rp['LOG'].map(extract)
    rp = rp[rp['USERNAME'].str.contains('WEBC_|webc_')]
    deb = deb[deb['USERNAME'].str.contains('WEBC_|webc_')]

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
    try:
        # Tentative de lecture des feuilles Excel
        df_1 = pd.read_excel(uploaded_file, sheet_name='unlock', parse_dates=['Timestamp'])
        df_2 = pd.read_excel(uploaded_file, sheet_name='reset_pin', parse_dates=['Timestamp'])

        # Mise à jour de l'activité de l'utilisateur
        st.session_state["last_active"] = time.time()

    except Exception as e:
        # Affichage d'un message d'erreur convivial
        st.error("Veuillez vous assurer que le fichier respecte le template approprié.")
        st.stop()
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
    st.session_state["last_active"] = time.time()

    if start_date > end_date:
        st.error("⚠ La date de début doit être antérieure ou égale à la date de fin.")
    # --------------------------------------
    # 3. Appel de la fonction de reporting
    # --------------------------------------
    reporting_type = st.selectbox(
        "Choisir le reporting à afficher :",
        ["-- Sélectionnez --", "Déblocage", "Réinitialisation Agent"],
        index=0  # Option par défaut = placeholder
    )
    if reporting_type == "-- Sélectionnez --":
        st.stop()  # ou affiche un message
    if st.button("Générer le rapport"):
        # Filtrage des données selon les dates choisies
        mask_1 = df_1["Timestamp"].dt.date.between(start_date, end_date)
        mask_2 = df_2["Timestamp"].dt.date.between(start_date, end_date)
        df_1 = df_1[mask_1]
        df_2 = df_2[mask_2]
        deb_report, agent_report = mm_report(df_1, df_2)
        left_col, right_col = st.columns([3, 1])
        if reporting_type == "Déblocage":
            left_col.subheader("Point des déblocages")
            left_col.write(style_dataframe(deb_report).to_html(),
                               unsafe_allow_html=True)
            right_col.markdown(f"""
            # 
            ##### ☑ Débloqué : {format_number(deb_report['UNLOCK'].sum())}
            ##### ☑ Réinitialisé : {format_number(deb_report['RESET_ONLY'].sum())}
            ##### ☑ Total : {format_number(deb_report['TOTAL'].sum())}
            """, unsafe_allow_html=True)
            to_export = deb_report
            st.session_state["last_active"] = time.time()
        else:
            left_col.subheader("Point des reset pin Agent")
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

