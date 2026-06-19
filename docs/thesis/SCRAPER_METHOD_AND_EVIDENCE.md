# Cara Menjelaskan dan Memasukkan Scraping ke Skripsi

Sumber teknis utama: `services/scraper/scraper.ipynb`.

## Posisi di Naskah

Masukkan scraping di dua tempat:

1. Bab 3, bagian metode pengumpulan data lowongan kerja.
2. Bab 4, bagian hasil implementasi artefak pengumpulan data dan bukti parser berjalan.

Jangan meletakkan scraping sebagai evaluasi akurasi model. Scraping hanya menjelaskan asal data lowongan dan proses pembentukan katalog sebelum data dipakai oleh SBERT, NCF, DQN, dan pipeline rekomendasi.

## Narasi Bab 3: Metode Pengumpulan Data Lowongan

Sistem SCPA menggunakan proses scraping untuk memperoleh data lowongan kerja dari halaman web atau respons publik yang berisi daftar lowongan. Implementasi dasar proses scraping ditunjukkan pada notebook `services/scraper/scraper.ipynb`. Notebook tersebut mendemonstrasikan tahapan ekstraksi data menggunakan BeautifulSoup, mulai dari membaca struktur HTML, memilih elemen kandidat lowongan, membersihkan teks, mengambil atribut penting lowongan, hingga menghapus duplikasi.

Tahapan scraping yang digunakan adalah sebagai berikut:

1. Mengambil sumber HTML lowongan kerja.
2. Melakukan parsing HTML menggunakan BeautifulSoup.
3. Mendeteksi elemen kandidat lowongan melalui selector umum seperti `[data-job]`, `.job`, `.job-card`, `.job-listing`, `.vacancy`, `article`, dan `li`.
4. Mengekstrak atribut lowongan, yaitu judul pekerjaan, perusahaan, lokasi, deskripsi, tag/skill, dan URL sumber.
5. Membersihkan teks dengan menghapus spasi berlebih agar data lebih konsisten.
6. Membuat `content_hash` dari kombinasi judul, perusahaan, dan lokasi untuk mendeteksi duplikasi.
7. Mengembalikan data dalam format terstruktur agar dapat diproses oleh pipeline rekomendasi.

Potongan metode ini dapat ditulis dalam skripsi sebagai berikut:

> Pada tahap pengumpulan data, sistem melakukan scraping lowongan kerja menggunakan parser HTML berbasis BeautifulSoup. Parser membaca elemen-elemen kandidat lowongan dari halaman sumber, kemudian mengekstrak atribut utama berupa judul pekerjaan, nama perusahaan, lokasi, deskripsi, tag/skill, dan URL sumber. Setelah data diekstraksi, sistem melakukan normalisasi teks untuk menghapus spasi berlebih dan membuat identitas konten (`content_hash`) dari kombinasi judul, perusahaan, dan lokasi. Identitas ini digunakan untuk menghindari duplikasi lowongan sebelum data diteruskan ke pipeline rekomendasi.

## Penjelasan Kode Notebook

Gunakan penjelasan berikut jika perlu membahas isi notebook:

- `clean_text()` membersihkan teks hasil scraping agar spasi, baris kosong, dan karakter berulang tidak membuat data berantakan.
- `first_text()` mencoba beberapa selector untuk mencari nilai pertama yang tersedia, misalnya judul dari `.job-title`, `h2`, `h3`, atau `a`.
- `tag_texts()` mengambil tag/skill dari elemen seperti `.tag`, `.tags li`, `[data-tag]`, `.chip`, dan `.badge`.
- `content_hash()` membuat hash SHA-256 dari `title`, `company`, dan `location`; 16 karakter awal dipakai sebagai identitas konten untuk deduplikasi.
- `extract_jobs()` adalah fungsi utama yang menggabungkan semua proses: parsing HTML, ekstraksi field, deduplikasi, dan pembatasan jumlah hasil.

## Narasi Bab 4: Hasil Implementasi Scraping

Di Bab 4, jangan hanya menulis bahwa scraper aktif. Tampilkan bukti dari notebook:

- screenshot cell fungsi `extract_jobs()`;
- screenshot output `result` yang menampilkan `count`, `jobs`, dan `deduplicated`;
- screenshot assertion `All scraper notebook assertions passed.`;
- bila ada bukti runtime live, tambahkan screenshot endpoint `/health` atau `/scrape/run`.

Contoh narasi Bab 4:

> Pengujian awal modul scraping dilakukan menggunakan notebook `services/scraper/scraper.ipynb`. Notebook tersebut menggunakan contoh HTML berisi tiga kartu lowongan, yaitu dua lowongan unik dan satu lowongan duplikat. Hasil eksekusi menunjukkan bahwa parser berhasil mengekstrak dua lowongan unik dengan field `title`, `description`, `company`, `location`, `tags`, `source_url`, dan `content_hash`. Satu lowongan duplikat berhasil dihapus, ditunjukkan oleh nilai `deduplicated = 1`. Assertion pada notebook juga berhasil dijalankan, sehingga logika dasar ekstraksi, pembersihan teks, dan deduplikasi dinyatakan berjalan sesuai skenario uji.

## Tabel yang Bisa Dimasukkan

| Tahap | Implementasi | Bukti |
| --- | --- | --- |
| Parsing HTML | BeautifulSoup membaca elemen lowongan dari selector umum | Cell fungsi `extract_jobs()` |
| Ekstraksi field | Mengambil judul, perusahaan, lokasi, deskripsi, tag, dan URL sumber | Output `result["jobs"]` |
| Pembersihan teks | `clean_text()` menghapus spasi berlebih | Output title/company/location rapi |
| Deduplikasi | `content_hash(title, company, location)` | `deduplicated = 1` pada contoh uji |
| Validasi notebook | Assertion memastikan jumlah dan field sesuai | `All scraper notebook assertions passed.` |

## Caption Gambar

Gunakan caption seperti ini:

- Gambar 4.x Tampilan fungsi ekstraksi lowongan pada notebook scraper.
- Gambar 4.x Hasil ekstraksi dua lowongan unik dan satu data duplikat yang berhasil dihapus.
- Gambar 4.x Bukti validasi notebook scraper dengan assertion berhasil.
- Gambar 4.x Endpoint kesehatan scraper pada runtime aplikasi, jika service scraper dijalankan.

## Batas Klaim

Notebook `services/scraper/scraper.ipynb` memakai contoh HTML lokal. Karena itu, klaim yang aman adalah:

- parser scraping berjalan;
- field lowongan berhasil diekstrak;
- teks berhasil dibersihkan;
- duplikasi sederhana berhasil dideteksi;
- output sudah berbentuk struktur data lowongan.

Klaim yang tidak boleh hanya memakai notebook ini:

- jumlah lowongan real di database;
- semua sumber job board berhasil di-scrape;
- scraper berjalan terus-menerus di production;
- data real selalu bersih tanpa validasi tambahan.

Untuk klaim tersebut, tambahkan bukti runtime dari service `services/scraper/main.py`, endpoint `/scrape/run`, tabel database `jobs`, atau laporan continuous scraper di `reports/debug/continuous_scrape/`.
