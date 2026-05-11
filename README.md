# C conversion scaffold

Bu proje Python dosyalarının C'ye çevrilmesi için başlangıç iskeletidir.

Linux / WSL derleme ve çalıştırma:

```sh
source .venv/bin/activate  # varsa
make
make run
make ui
make clean
```

Paylaşım için temiz arşiv oluşturma:

```sh
./package.sh
```

Çıktı: `bin/app`

Streamlit arayüzü için:

```sh
python3 -m streamlit run dashboard.py
```

Notlar:
- Bu sürüm, Python modüllerinin C karşılıklarını içerir.
- `make` çalıştırmak için bir C derleyicisi gerekir (`cc`/`gcc`). Debian/Ubuntu için genelde `build-essential` paketi yeterlidir.
- UI için `streamlit`, `pandas` ve diğer Python bağımlılıkları gerekir; bunlar `requirements.txt` içinde listelenir.
