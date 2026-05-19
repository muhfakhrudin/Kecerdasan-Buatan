import os
import re
import time
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- KONFIGURASI ---
URLS = [
    "https://www.tokopedia.com/goodponsel/etalase/second-iphone",
    "https://www.tokopedia.com/net-store168/etalase/iphone",
    "https://www.tokopedia.com/panda-jaya-gadget/etalase/iphone-11-series",
    "https://www.tokopedia.com/panda-jaya-gadget/etalase/iphone-12-series",
    "https://www.tokopedia.com/panda-jaya-gadget/etalase/iphone-13-series",
    "https://www.tokopedia.com/cyruscelluler/etalase/iphone-second-like-new",
    "https://www.tokopedia.com/mobilephonebec/etalase/iphone-11-series",
    "https://www.tokopedia.com/mobilephonebec/etalase/iphone-12-series",
    "https://www.tokopedia.com/mobilephonebec/etalase/iphone-13-series",
    "https://www.tokopedia.com/boboystore889-shop/etalase/iphone-1"
]

def extract_bh(text):
    if not text:
        return None
    
    # Hapus tag HTML secara kasar jika ada, dan ubah newline menjadi spasi
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('\n', ' ')
    
    # Cari beberapa variasi penulisan battery health / kondisi baterai
    # [\s=:-]* akan cocok dengan spasi berapapun, tanda sama dengan, titik dua, atau strip
    patterns = [
        r"(?:BH|B\.H\.|Battery Health|battery health|baterai health|Kesehatan Baterai|kondisi baterai|kapasitas maksimal)[\s=:-]*(\d{2,3})%?",
        r"(\d{2,3})\s?%?[\s=:-]*(?:battery|baterai|bh|b\.h\.)",
        r"battery[\s=:-]*(\d{2,3})%",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1)
            # Pastikan nilainya masuk akal untuk persentase baterai (misal 50 - 100)
            if val.isdigit() and 50 <= int(val) <= 100:
                return val
    return None

def fetch_product_description(url, driver):
    """Fetch deskripsi produk menggunakan Selenium."""
    try:
        current_handle = driver.current_window_handle
        driver.execute_script("window.open(arguments[0]);", url)
        time.sleep(2)
        handles = driver.window_handles
        new_handle = [h for h in handles if h != current_handle][-1]
        driver.switch_to.window(new_handle)
        time.sleep(6) # Tunggu render
        
        deskripsi = ""
        try:
            # Mencoba mencari elemen deskripsi spesifik Tokopedia
            desc_element = driver.find_element(By.XPATH, "//*[@data-testid='lblPDPDescriptionProduk']")
            deskripsi = desc_element.text
        except:
            try:
                # Fallback ambil body text jika elemen spesifik tidak ketemu
                deskripsi = driver.find_element(By.TAG_NAME, "body").text
            except:
                pass
            
        driver.close()
        driver.switch_to.window(current_handle)
        
        if deskripsi:
            # Bersihkan spasi berlebih dan enter agar rapi di CSV
            deskripsi = " ".join(deskripsi.split())
            return deskripsi
    except Exception as e:
        print(f"[DEBUG] Fetch URL (selenium) gagal: {e}")
        try:
            driver.switch_to.window(current_handle)
        except:
            pass
    return None

chrome_options = Options()
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_argument('--start-maximized')
chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

def create_driver():
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

driver = create_driver()
all_data = []

def safe_execute_script(driver, script, *args):
    """Execute script dengan fallback jika driver crash"""
    try:
        return driver.execute_script(script, *args)
    except Exception as e:
        return None

try:
    for url in URLS:
        print(f"\n>>> Mengakses: {url.split('/')[3]}")
        try:
            driver.get(url)
            time.sleep(12) # Menunggu render
        except Exception as e:
            print(f"[ERROR] Gagal membuka URL atau driver crash: {e}")
            try:
                driver.quit()
            except:
                pass
            driver = create_driver()  # Restart driver
            print("[INFO] Driver di-restart, lanjut ke URL berikutnya")
            continue

        # Scroll lebih minimal untuk menghindari crash
        for scroll_idx in range(3):
            try:
                safe_execute_script(driver, "window.scrollBy(0, 600);")
                time.sleep(1)
            except Exception as e:
                print(f"[WARNING] Scroll {scroll_idx} gagal: {e}")
                break

        # STRATEGI BARU: Cari semua elemen yang mengandung class 'pcv3__container' 
        # atau 'prd_container-card' (Ini adalah box produk Tokopedia)
        try:
            cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'pcv3__container') or contains(@class, 'prd_container-card')]")
            
            # JIKA MASIH 0: Gunakan cara paling brutal, ambil semua div yang punya teks "Rp"
            if len(cards) == 0:
                cards = driver.find_elements(By.XPATH, "//div[.//div[contains(text(), 'Rp')]]")

            print(f"Berhasil mendeteksi {len(cards)} box produk.")

            shop_name = url.split('/')[3]
            for idx, card in enumerate(cards):
                try:
                    # Ambil semua teks di dalam box produk dan bersihkan
                    full_text = card.text
                    lines = full_text.split('\n')
                    
                    # Biasanya Nama Produk ada di baris pertama, Harga ada di baris yang mengandung 'Rp'
                    nama = lines[0] if lines else "Unknown"
                    harga = next((s for s in lines if "Rp" in s), "0")
                    
                    low_nama = nama.lower()
                    if any(x in low_nama for x in ["iphone 11", "iphone 12", "iphone 13"]):
                        deskripsi = ""
                        try:
                            a = card.find_element(By.XPATH, ".//a[@href]")
                            href = a.get_attribute('href')
                            if href and (href.startswith('http') or href.startswith('/')):
                                # Pastikan URL lengkap
                                if href.startswith('/'):
                                    href = 'https://www.tokopedia.com' + href
                                print(f"  → Fetch deskripsi: {href[:80]}...")
                                fetched_desc = fetch_product_description(href, driver=driver)
                                if fetched_desc:
                                    deskripsi = fetched_desc
                        except Exception as e:
                            pass

                        if deskripsi:
                            all_data.append({
                                "Toko": shop_name,
                                "Seri": nama,
                                "Deskripsi": deskripsi,
                                "Harga": harga
                            })
                        else:
                            print(f"  → Dilewati (gagal ambil deskripsi): {nama[:60]}...")
                except Exception as card_e:
                    pass  # Silent skip problematic card
                    continue
        except Exception as url_e:
            print(f"[ERROR] Gagal proses URL {url}: {url_e}")

    if all_data:
        df = pd.DataFrame(all_data)
        # Deduplicate
        df_unique = df.drop_duplicates(subset=['Toko', 'Seri', 'Harga'], keep='first')
        df_unique.to_csv("data_iphone_v2.csv", index=False)
        print(f"\nSUKSES! {len(df_unique)} data tersimpan di data_iphone_v2.csv")
    else:
        print("\n[GAGAL] Tetap 0. Browser terdeteksi atau selector salah.")

finally:
    driver.quit()