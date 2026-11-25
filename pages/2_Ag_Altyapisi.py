from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ağ Altyapısı", page_icon="🌐", layout="wide")
st.title("🌐 Ağ Altyapısı")
st.caption("Keşfedilen ağ ekipmanları ve altyapı adayları")

path = Path("data/processed/infrastructure_candidates.csv")
if not path.exists():
    st.warning("Henüz altyapı verisi yok. Önce ana taramayı çalıştırın.")
    st.stop()

df = pd.read_csv(path, encoding="utf-8-sig").fillna("")
if df.empty:
    st.info("Henüz ağ altyapısı cihazı adayı bulunamadı.")
    st.stop()

types = sorted({part.strip() for value in df["candidate_type"].astype(str) for part in value.split(";") if part.strip()})
selected = st.multiselect("Cihaz türü", types, default=types)
filtered = df[df["candidate_type"].apply(lambda value: any(part in selected for part in str(value).split(";")))]

a, b = st.columns(2)
a.metric("Toplam aday", len(df))
b.metric("Filtrelenmiş cihaz", len(filtered))
st.info("Adaylar sınıflandırma verilerinden çıkarılmıştır; fiziksel bağlantıları henüz doğrulanmamıştır.")

columns = ["ip", "mac", "hostname", "candidate_type", "vendor", "vendor_role", "confidence", "verification_status"]
st.dataframe(filtered[[column for column in columns if column in filtered.columns]], use_container_width=True, hide_index=True)
st.download_button("CSV olarak indir", filtered.to_csv(index=False).encode("utf-8-sig"), "ag_altyapisi.csv", "text/csv")
