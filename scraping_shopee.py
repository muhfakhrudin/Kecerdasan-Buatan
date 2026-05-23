import os
import re
import time
import random
import json
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
#  KONFIGURASI
# ============================================================

# Path ke profil Chrome Anda (pastikan Chrome TERTUTUP saat menjalankan script ini!)
# Untuk menemukan path Anda: buka Chrome → ketik chrome://version → lihat "Profile Path"
CHROME_USER_DATA_DIR = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
CHROME_PROFILE = "Default"  # Ganti ke "Profile 1", "Profile 2", dst jika pakai profil lain

# Keyword pencarian iPhone bekas di Shopee
SEARCH_QUERIES = [
    "iphone x second",
    "iphone xr second",
    "iphone xs second",
    "iphone 11 second",
    "iphone 12 second",
    "iphone 13 second",
]

# Maksimal halaman per keyword (1 halaman ≈ 60 produk)
MAX_PAGES = 2

# File output
OUTPUT_FILE = "data_shopee.csv"


# ============================================================
#  FUNGSI PARSING (sama dengan scraping_iphone.py)
# ============================================================

def extract_bh(text):
    """Ekstrak Battery Health dari teks deskripsi."""
    if not text:
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


def extract_seri(nama):
    """Ekstrak nama model iPhone dari judul produk."""
    if not isinstance(nama, str):
        return "Unknown"

    nama_lower = nama.lower()

    models = [
        ("iphone 13 pro max", "iPhone 13 Pro Max"),
        ("iphone 13 promax", "iPhone 13 Pro Max"),
        ("iphone 13 pro", "iPhone 13 Pro"),
        ("iphone 13 mini", "iPhone 13 Mini"),
        ("iphone 13", "iPhone 13"),
        ("iphone 12 pro max", "iPhone 12 Pro Max"),
        ("iphone 12 promax", "iPhone 12 Pro Max"),
        ("iphone 12 pro", "iPhone 12 Pro"),
        ("iphone 12 mini", "iPhone 12 Mini"),
        ("iphone 12", "iPhone 12"),
        ("iphone 11 pro max", "iPhone 11 Pro Max"),
        ("iphone 11 promax", "iPhone 11 Pro Max"),
        ("iphone 11 pro", "iPhone 11 Pro"),
        ("iphone 11", "iPhone 11"),
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


def extract_kategori_seri(seri):
    """Tentukan kategori series dari nama model."""
    if "13" in seri:
        return "iPhone 13 Series"
    elif "12" in seri:
        return "iPhone 12 Series"
    elif "11" in seri:
        return "iPhone 11 Series"
    elif any(x in seri.lower() for x in ["iphone x", "iphone 10"]):
        return "iPhone X Series"
    return "Unknown"


def extract_kategori_varian(nama):
    """Ekstrak kapasitas penyimpanan dari judul produk."""
    if not isinstance(nama, str):
        return "Unknown"

    matches = re.findall(r'(\d+)\s*(?:GB|gb|Gb|TB|tb)', nama)
    if matches:
        variants = [f"{m}GB" for m in matches]
        return "/".join(variants)

    return "Unknown"


# ============================================================
#  FUNGSI UTILITAS
# ============================================================

def human_delay(min_sec=3, max_sec=7):
    """Delay acak agar terlihat seperti manusia."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def human_scroll(driver, scroll_count=5):
    """Scroll halaman secara bertahap seperti manusia."""
    for i in range(scroll_count):
        scroll_px = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_px});")
        time.sleep(random.uniform(0.8, 2.0))


def is_iphone_product(nama):
    """Cek apakah judul produk mengandung nama iPhone yang relevan (bukan aksesoris)."""
    if not isinstance(nama, str):
        return False

    low = nama.lower()

    # Kata-kata yang menandakan produk BUKAN iPhone unit
    blacklist = [
        "case", "casing", "tempered", "screen protector", "anti gores",
        "charger", "kabel", "cable", "adaptor", "adapter", "softcase",
        "hardcase", "silikon", "silicon", "skin", "garskin", "sticker",
        "dummy", "magsafe", "airpods", "airpod", "apple watch",
        "ipad", "macbook", "imac", "earphone", "headset", "holder",
        "ring", "stand", "docking", "powerbank", "power bank",
        "sim tray", "baterai replacement", "lcd replacement", "sparepart",
    ]

    if any(b in low for b in blacklist):
        return False

    # Harus mengandung keyword iPhone yang relevan
    keywords = ["iphone 11", "iphone 12", "iphone 13",
                "iphone x", "iphone 10", "iphone xs", "iphone xr"]
    return any(k in low for k in keywords)


# ============================================================
#  FUNGSI SCRAPING SHOPEE
# ============================================================

def create_driver():
    """Buat instance Chrome yang tidak terdeteksi, menggunakan profil login user."""
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={CHROME_PROFILE}")
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver


def check_login(driver):
    """Buka Shopee dan cek apakah sudah login."""
    print("[INFO] Memeriksa status login Shopee...")
    driver.get("https://shopee.co.id/")
    human_delay(5, 8)

    page_source = driver.page_source.lower()

    # Jika ada tombol "Daftar" / "Login" di navbar, kemungkinan belum login
    # Jika ada elemen profil/akun, berarti sudah login
    try:
        # Coba cari elemen navbar yang menunjukkan status login
        # Di Shopee, user yang sudah login akan menampilkan nama/username di navbar
        navbar_text = driver.find_element(By.CSS_SELECTOR, "div.navbar__username, li.navbar__link--account__container").text
        if navbar_text:
            print(f"[OK] Login terdeteksi sebagai: {navbar_text}")
            return True
    except:
        pass

    # Fallback: cek apakah halaman "buyer/login" muncul
    if "/buyer/login" in driver.current_url:
        print("[WARNING] Anda belum login ke Shopee!")
        print("[INFO] Silakan login secara manual di jendela Chrome yang terbuka...")
        print("[INFO] Tekan ENTER di terminal ini setelah berhasil login...")
        input()
        return True

    # Jika tidak bisa memastikan, anggap sudah login dan lanjutkan
    print("[INFO] Status login tidak bisa dipastikan, melanjutkan scraping...")
    return True


def fetch_product_detail(driver, url):
    """Buka halaman detail produk Shopee dan ambil deskripsi."""
    try:
        current_handle = driver.current_window_handle
        driver.execute_script("window.open(arguments[0]);", url)
        human_delay(2, 4)

        handles = driver.window_handles
        new_handle = [h for h in handles if h != current_handle][-1]
        driver.switch_to.window(new_handle)
        human_delay(4, 8)

        # Scroll sedikit agar deskripsi ter-load
        human_scroll(driver, scroll_count=3)
        human_delay(2, 4)

        deskripsi = ""
        try:
            # Shopee: deskripsi biasanya ada di section dengan class tertentu
            selectors = [
                "div.product-detail p",
                "div[class*='product-detail'] span",
                "div[class*='description'] p",
                "div[class*='Description'] span",
                # Shopee modern layout
                "div[class*='f7AU53']",
                "div[class*='GUZfxA']",
                # Fallback: cari div yang mengandung teks panjang (>100 char)
            ]

            for sel in selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    for elem in elems:
                        text = elem.text.strip()
                        if len(text) > 100:
                            deskripsi = text
                            break
                except:
                    continue
                if deskripsi:
                    break

            # Fallback terakhir: ambil semua teks halaman dan cari bagian deskripsi
            if not deskripsi:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                # Cari section yang mengandung keyword deskripsi
                if "DESKRIPSI" in body_text.upper() or "BATTERY" in body_text.upper():
                    deskripsi = body_text

        except Exception as e:
            print(f"  [DEBUG] Gagal ambil deskripsi: {e}")

        driver.close()
        driver.switch_to.window(current_handle)

        if deskripsi:
            deskripsi = " ".join(deskripsi.split())
            return deskripsi

    except Exception as e:
        print(f"  [ERROR] Fetch detail gagal: {e}")
        try:
            driver.switch_to.window(current_handle)
        except:
            pass
    return None


def scrape_search_page(driver, query, page=0):
    """Scrape satu halaman pencarian Shopee."""
    products = []

    # Buat URL pencarian Shopee
    encoded_query = query.replace(" ", "+")
    url = f"https://shopee.co.id/search?keyword={encoded_query}&page={page}&sortBy=relevancy"

    print(f"\n>>> Membuka: {url}")
    driver.get(url)
    human_delay(5, 10)

    # Scroll untuk memuat semua produk (lazy-loading)
    human_scroll(driver, scroll_count=8)
    human_delay(2, 4)

    # Cari card produk Shopee
    # Shopee menggunakan berbagai class yang sering berubah,
    # jadi kita coba beberapa selector
    card_selectors = [
        "li.shopee-search-item-result__item",
        "div[data-sqe='item']",
        "a[data-sqe='link']",
        # Shopee modern: card produk biasanya di dalam li di search grid
        "ul.row > li",
        # Fallback: cari semua link yang mengarah ke halaman produk
    ]

    cards = []
    for sel in card_selectors:
        try:
            found = driver.find_elements(By.CSS_SELECTOR, sel)
            if len(found) > 5:  # Minimal 5 card agar valid
                cards = found
                print(f"  Ditemukan {len(cards)} card produk (selector: {sel})")
                break
        except:
            continue

    # Fallback: cari semua <a> yang href-nya mengarah ke produk Shopee
    if not cards:
        try:
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='-i.']")
            if all_links:
                cards = all_links
                print(f"  Ditemukan {len(cards)} link produk (fallback)")
        except:
            pass

    if not cards:
        print("  [WARNING] Tidak ada produk ditemukan di halaman ini")
        return products

    for idx, card in enumerate(cards):
        try:
            # Ambil teks dari card
            card_text = card.text
            if not card_text:
                continue

            lines = card_text.strip().split('\n')
            if len(lines) < 2:
                continue

            # Nama produk biasanya di baris pertama
            nama = lines[0].strip()

            # Cek apakah ini produk iPhone yang valid
            if not is_iphone_product(nama):
                continue

            # Cari harga (baris yang mengandung angka dengan format harga)
            harga = "0"
            for line in lines:
                # Format Shopee: "Rp1.234.567" atau "1.234.567"
                if re.search(r'(?:Rp\.?\s?)?[\d]+\.[\d]+\.[\d]+', line):
                    harga_match = re.search(r'((?:Rp\.?\s?)?[\d]+\.[\d]+\.[\d]+)', line)
                    if harga_match:
                        harga = harga_match.group(1)
                        if not harga.startswith("Rp"):
                            harga = "Rp" + harga
                        break

            # Cari nama toko (biasanya ada di card Shopee)
            toko = "Unknown"
            for line in lines:
                # Toko biasanya setelah lokasi atau sebelum rating
                line_lower = line.lower().strip()
                # Skip baris yang jelas bukan nama toko
                if any(skip in line_lower for skip in ["rp", "terjual", "rating", "%", "gratis ongkir", "cod", "star", "iklan"]):
                    continue
                if line_lower == nama.lower():
                    continue
                # Jika baris pendek dan bukan angka, kemungkinan ini nama toko atau lokasi
                if 3 < len(line.strip()) < 40 and not line.strip().isdigit():
                    toko = line.strip()

            # Coba ambil link ke halaman detail
            product_url = None
            try:
                link_elem = card if card.tag_name == 'a' else card.find_element(By.CSS_SELECTOR, "a[href*='-i.']")
                href = link_elem.get_attribute("href")
                if href and "-i." in href:
                    product_url = href if href.startswith("http") else "https://shopee.co.id" + href
            except:
                pass

            products.append({
                "nama": nama,
                "harga": harga,
                "toko": toko,
                "url": product_url
            })

        except Exception as e:
            continue

    print(f"  Produk iPhone valid: {len(products)}")
    return products


# ============================================================
#  MAIN
# ============================================================

def main():
    print("=" * 60)
    print(" SHOPEE IPHONE SCRAPER (Login via Chrome Profile)")
    print("=" * 60)
    print(f"\nChrome Profile: {CHROME_USER_DATA_DIR}")
    print(f"Search Queries: {SEARCH_QUERIES}")
    print(f"Max Pages: {MAX_PAGES}")
    print(f"Output: {OUTPUT_FILE}")
    print()
    print("[PENTING] Pastikan semua jendela Chrome SUDAH TERTUTUP!")
    print()

    driver = None
    all_data = []

    try:
        driver = create_driver()
        human_delay(3, 5)

        # Cek login Shopee
        if not check_login(driver):
            print("[FATAL] Tidak bisa melanjutkan tanpa login Shopee.")
            return

        # Loop setiap keyword pencarian
        for query in SEARCH_QUERIES:
            print(f"\n{'='*50}")
            print(f"PENCARIAN: '{query}'")
            print(f"{'='*50}")

            for page in range(MAX_PAGES):
                print(f"\n--- Halaman {page + 1} ---")
                products = scrape_search_page(driver, query, page)

                if not products:
                    print(f"  Tidak ada produk, skip halaman selanjutnya")
                    break

                # Ambil detail deskripsi untuk setiap produk
                for i, prod in enumerate(products):
                    print(f"\n  [{i+1}/{len(products)}] {prod['nama'][:60]}...")

                    deskripsi = ""
                    if prod["url"]:
                        print(f"    → Fetch deskripsi: {prod['url'][:70]}...")
                        deskripsi = fetch_product_detail(driver, prod["url"]) or ""
                        human_delay(2, 5)  # Delay antar fetch

                    seri = extract_seri(prod["nama"])
                    kategori_seri = extract_kategori_seri(seri)
                    penyimpanan = extract_kategori_varian(prod["nama"])
                    battery_health = extract_bh(deskripsi)

                    all_data.append({
                        "Toko": prod["toko"],
                        "Platform": "Shopee",
                        "Kategori Seri": kategori_seri,
                        "Kategori Varian": seri,
                        "penyimpanan": penyimpanan,
                        "Battery Health": battery_health if battery_health else "N/A",
                        "Harga": prod["harga"]
                    })

                # Delay antar halaman
                human_delay(3, 6)

            # Delay antar keyword
            human_delay(5, 10)

        # Simpan ke CSV
        if all_data:
            df = pd.DataFrame(all_data)
            # Hapus Unknown seri
            df = df[df["Kategori Varian"] != "Unknown"]
            # Deduplicate
            df_unique = df.drop_duplicates(
                subset=["Toko", "Kategori Varian", "penyimpanan", "Harga"],
                keep="first"
            )
            df_unique.to_csv(OUTPUT_FILE, index=False)
            print(f"\n{'='*60}")
            print(f"SUKSES! {len(df_unique)} data tersimpan di {OUTPUT_FILE}")
            print(f"Kolom: {list(df_unique.columns)}")
            print(f"{'='*60}")

            # Preview
            print("\n--- PREVIEW DATA ---")
            print(df_unique.to_string(index=False))
        else:
            print("\n[GAGAL] Tidak ada data yang berhasil diambil.")
            print("Kemungkinan penyebab:")
            print("  1. Anda belum login ke Shopee di Chrome")
            print("  2. Shopee mendeteksi aktivitas bot")
            print("  3. Selector CSS Shopee telah berubah")

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        print("\n[INFO] Browser ditutup. Selesai.")


if __name__ == "__main__":
    main()
