@echo off
cd /d "D:\Portofolio\news-summarizer\scrapers"

:: Force Windows/Python to support all Unicode characters in logs
set PYTHONIOENCODING=utf-8

:: The >> logs.txt sends all outputs and errors to a file
echo --- Run started at %date% %time% --- >> logs.txt

:: Run tribun scraper for multiple categories
python tribun_scraper.py -c business -l 60 -o ./outputs/tribun_business.json >> logs.txt 2>&1
python .\tribun_scraper.py -c nasional -l 60 -o ./outputs/tribun_nasional.json >> logs.txt 2>&1
python .\tribun_scraper.py -c finansial -l 60 -o ./outputs/tribun_finansial.json >> logs.txt 2>&1
python .\tribun_scraper.py -c sport -l 60 -o ./outputs/tribun_sport.json >> logs.txt 2>&1

:: Run detik scraper for multiple categories
python detik_finance_scraper.py -c finance -l 60 -o ./outputs/detik_finance.json >> logs.txt 2>&1
python detik_finance_scraper.py -c energi -l 60 -o ./outputs/detik_energi.json >> logs.txt 2>&1
python detik_finance_scraper.py -c business -l 60 -o ./outputs/detik_business.json >> logs.txt 2>&1
python detik_finance_scraper.py -c moneter -l 60 -o ./outputs/detik_moneter.json >> logs.txt 2>&1

:: Run antara scraper for multiple categories
python .\antara_scraper.py -c ekonomi -l 60 -o ./outputs/antara_ekonomi.json >> logs.txt 2>&1
python .\antara_scraper.py -c bisnis -l 60 -o ./outputs/antara_bisnis.json >> logs.txt 2>&1
python .\antara_scraper.py -c finansial -l 60 -o ./outputs/antara_finansial.json >> logs.txt 2>&1
python .\antara_scraper.py -c politik -l 60 -o ./outputs/antara_politik.json >> logs.txt 2>&1

:: Run berita satu scraper for multiple categories
:: python .\berita_satu.py -c ekonomi -l 60 -o ./outputs/beritasatu_ekonomi.json >> logs.txt 2>&1
:: python .\berita_satu.py -c nasional -l 60 -o ./outputs/beritasatu_nasional.json >> logs.txt 2>&1
:: python .\berita_satu.py -c teknologi -l 60 -o ./outputs/beritasatu_teknologi.json >> logs.txt 2>&1
:: python .\berita_satu.py -c olahraga -l 60 -o ./outputs/beritasatu_olahraga.json >> logs.txt 2>&1

:: Upload to Google Sheets
python upload.py >> logs.txt 2>&1

echo --- Run ended --- >> logs.txt   