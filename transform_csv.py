import re
import pandas as pd

# --- Baca CSV asli ---
df = pd.read_csv("data_iphone_v2.csv")

print(f"Total baris awal: {len(df)}")
print(f"Kolom awal: {list(df.columns)}")

# --- Fungsi extract Battery Health dari Deskripsi ---
def extract_bh(text):
    if not isinstance(text, str) or not text:
        return None
    
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('\n', ' ')
    
    patterns = [
        r"(?:BH|B\.H\.|Battery Health|battery health|baterai health|Kesehatan Baterai|kondisi baterai|kapasitas maksimal)[\s=:-]*(\d{2,3})%?",
        r"(\d{2,3})\s?%?[\s=:-]*(?:battery|baterai|bh|b\.h\.)",
        r"battery[\s=:-]*(\d{2,3})%",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1)
            if val.isdigit() and 50 <= int(val) <= 100:
                return val
    return None


# --- Fungsi extract Seri iPhone (hanya nama model) ---
def extract_seri(nama):
    if not isinstance(nama, str):
        return "Unknown"
    
    nama_lower = nama.lower()
    
    # Daftar model iPhone yang mungkin muncul (urut dari yang paling spesifik)
    models = [
        # iPhone 13 series
        ("iphone 13 pro max", "iPhone 13 Pro Max"),
        ("iphone 13 promax", "iPhone 13 Pro Max"),
        ("iphone 13 pro", "iPhone 13 Pro"),
        ("iphone 13 mini", "iPhone 13 Mini"),
        ("iphone 13", "iPhone 13"),
        # iPhone 12 series
        ("iphone 12 pro max", "iPhone 12 Pro Max"),
        ("iphone 12 promax", "iPhone 12 Pro Max"),
        ("iphone 12 pro", "iPhone 12 Pro"),
        ("iphone 12 mini", "iPhone 12 Mini"),
        ("iphone 12", "iPhone 12"),
        # iPhone 11 series
        ("iphone 11 pro max", "iPhone 11 Pro Max"),
        ("iphone 11 promax", "iPhone 11 Pro Max"),
        ("iphone 11 pro", "iPhone 11 Pro"),
        ("iphone 11", "iPhone 11"),
        # iPhone X / 10 series
        ("iphone xs max", "iPhone XS Max"),
        ("iphone xsmax", "iPhone XS Max"),
        ("iphone xs", "iPhone XS"),
        ("iphone xr", "iPhone XR"),
        ("iphone x", "iPhone X"),
        ("iphone 10", "iPhone X"),
    ]
    
    for keyword, model_name in models:
        if keyword in nama_lower:
            return model_name
    
    return "Unknown"


# --- Fungsi extract Kategori Seri ---
def extract_kategori_seri(seri):
    if "13" in seri:
        return "iPhone 13 Series"
    elif "12" in seri:
        return "iPhone 12 Series"
    elif "11" in seri:
        return "iPhone 11 Series"
    elif any(x in seri.lower() for x in ["iphone x", "iphone 10"]):
        return "iPhone X Series"
    return "Unknown"


# --- Fungsi extract Kategori Varian (kapasitas storage) dari nama produk ---
def extract_kategori_varian(nama):
    if not isinstance(nama, str):
        return "Unknown"
    
    # Cari semua kapasitas yang disebutkan di nama produk
    # Pattern: angka diikuti GB atau TB (case insensitive)
    matches = re.findall(r'(\d+)\s*(?:GB|gb|Gb|TB|tb)', nama)
    
    if matches:
        # Gabungkan semua varian yang ditemukan
        variants = [f"{m}GB" for m in matches]
        return "/".join(variants)
    
    return "Unknown"


# --- Transformasi data ---
new_data = []

for _, row in df.iterrows():
    toko = row['Toko']
    nama_produk = row['Seri']  # Kolom "Seri" asli berisi nama produk lengkap
    deskripsi = row.get('Deskripsi', '')
    harga = row['Harga']
    
    seri = extract_seri(nama_produk)
    kategori_seri = extract_kategori_seri(seri)
    kategori_varian = extract_kategori_varian(nama_produk)
    battery_health = extract_bh(deskripsi)
    
    new_data.append({
        "Toko": toko,
        "Platform": "Tokopedia",
        "Seri": seri,
        "Kategori Seri": kategori_seri,
        "Kategori Varian": kategori_varian,
        "Battery Health": battery_health if battery_health else "N/A",
        "Harga": harga
    })

# --- Buat DataFrame baru & simpan ---
df_new = pd.DataFrame(new_data)

# Tampilkan preview
print("\n--- PREVIEW DATA BARU ---")
print(df_new.to_string(index=False))

# Simpan ke file yang sama
df_new.to_csv("data_iphone_v2.csv", index=False)
print(f"\nSUKSES! {len(df_new)} baris data tersimpan ke data_iphone_v2.csv")
print(f"Kolom baru: {list(df_new.columns)}")
