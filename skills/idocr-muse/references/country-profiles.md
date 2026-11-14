# Country Profiles for ID Document Extraction

Field labels, date formats, and ID number patterns for each supported country.
Use this reference when extending or debugging the extraction logic in `scripts/extract_id.py`.

---

## China 🇨🇳 — 身份证 (National ID Card)

**Tesseract language:** `chi_sim+eng`

| Field label | English | Field name | Format / Notes |
|---|---|---|---|
| 姓名 | Full Name | `name_full` | 2–4 Chinese characters. Split via surname table. |
| 性别 | Gender | `gender` | 男=M, 女=F |
| 民族 | Ethnicity | `ethnicity` | e.g. 汉, 回, 藏, 维吾尔 |
| 出生 | Date of Birth | `dob` | YYYY年MM月DD日 |
| 住址 | Address | `address` | Multi-line, often followed by postal code |
| 公民身份号码 | ID Number | `id_number` | 18-digit: `\d{6}[1-9]\d{3}(?:0[1-9]\|1[0-2])(?:0[1-9]\|[12]\d\|3[01])\d{3}[\dXx]` |
| 签发机关 | Authority | `authority` | Issuing organ |
| 有效期限 | Validity | `validity` | Valid date range |

### Name splitting
- Name is one continuous block: 陈伟
- Single-char surnames (~80%): 陈, 王, 李, 张, 刘, 杨, 黄, 赵, 周, 吴, 徐, 孙, 马, 朱, 胡, 郭, 何, 高, 林, 罗, 郑, 梁, 谢, 宋, 唐, 韩, 曹, 许, 邓, 萧, 冯, 曾, 程, 蔡, 彭, 潘, 袁, 于, 董, 余, 苏, 叶, 吕, 魏, 蒋, 田, 杜, 丁, 沈, 任, 姚, 卢, 傅, 钟, 崔, 廖, 谭, 汪, 范, 金, 方, 石, 夏, 熊, 秦, 邱, 侯, 白, 江, 史, 龙, 万, 段, 雷, 钱, 汤, 尹, 黎, 易, 常, 武, 乔, 贺, 赖, 龚, 文
- Compound surnames (~20%): 欧阳, 司马, 上官, 夏侯, 诸葛, 司徒, 慕容, 独孤, 公孙, 宇文, 尉迟, 皇甫, 长孙, etc.
- Greedy compound match first, then single-char

---

## China 🇨🇳 — 护照 (Passport)

**Tesseract language:** `chi_sim+eng`

| Field label | English | Field name | Format / Notes |
|---|---|---|---|
| 姓名/Name | Name | surname_en + given_name_en | SURNAME GIVEN (Latin capitals) |
| 性别/Sex | Gender | `gender` | M/F |
| 出生日期/Date of birth | DOB | `dob` | YYYY-MM-DD or YYYY年MM月DD日 |
| 护照号/Passport No. | Passport number | `id_number` | E + 8 digits, or G + 8 digits |
| 签发机关/Authority | Authority | — | — |
| 有效期至/Date of expiry | Expiry | — | — |

**MRZ line 2** contains the passport number, nationality, DOB, sex, and expiry in ICAO 9303 format.

---

## Hong Kong 🇭🇰 — 香港身份证 (HKID)

**Tesseract language:** `chi_tra+eng`

| Field label | English | Field name | Format / Notes |
|---|---|---|---|
| 中文姓名 | Chinese Name | `name_chinese` | Chinese characters |
| 英文姓名 | English Name | `name_english` | SURNAME, Given names |
| 出生日期 | Date of Birth | `dob` | DD-MM-YYYY |
| 身份證號碼 | Identity Card Number | `id_number` | `[A-Z]\d{6}(\d)` — 1 letter + 6 digits + check digit in parentheses |
| 簽發日期 | Issue Date | `issue_date` | DD-MM-YYYY |

### Name parsing
- Chinese name: single block → split via surname table
- English name: comma-separated, `SURNAME, Given names` → CHAN, Tai Man

### Date format
- Always DD-MM-YYYY — unambiguous for this document type
- Example: 15-03-1985 → [DOB]5

---

## Japan 🇯🇵 — 旅券 (Passport)

**Tesseract language:** `jpn+eng`

| Field label | English | Field name | Format / Notes |
|---|---|---|---|
| 氏名 | Surname | `surname_raw` | Japanese name (kanji/kana) |
| Surname | Surname (Romaji) | `surname_en` | Latin capitals |
| 名前 | Given Names | `given_name_raw` | Japanese name (kanji/kana) |
| Given Names | Given Names (Romaji) | `given_name_en` | Latin capitals |
| 生年月日 | Date of Birth | `dob` | YYYY.MM.DD |
| Date of birth | DOB (alt) | — | DD.MM.YYYY (variant) |
| 性別 | Sex | `gender_char` | 男/女 |
| Sex | Sex | `gender_en` | M/F |
| 旅券番号 | Passport Number | `id_number` | `[A-Z]{2}\d{7}` — 2 letters + 7 digits |
| 国籍 | Nationality | `nationality_raw` | Japanese or JAPAN |
| Nationality | Nationality (alt) | `nationality_en` | JAPAN |

### Name parsing
- Document has separate fields for surname and given names — no splitting needed
- Japanese names in kanji/kana; Romaji in Latin capitals

### Date format
- Primary: YYYY.MM.DD (e.g. 1990.04.01)
- Also: DD.MM.YYYY variant on some versions
- MRZ: YYMMDD

---

## Japan 🇯🇵 — マイナンバー (My Number Card)

**Tesseract language:** `jpn+eng`

| Field label | English | Field name | Format / Notes |
|---|---|---|---|
| 氏名 | Name | — | Full name in Japanese |
| 生年月日 | Date of Birth | `dob` | YYYY年MM月DD日 or YYYY.MM.DD |
| 個人番号 | My Number | `id_number` | 12 digits |
| 性別 | Sex | `gender` | — |

---

## Russia 🇷🇺 — Загранпаспорт (International Passport)

**Tesseract language:** `rus+eng`

| Field label | English | Field name | Format / Notes |
|---|---|---|---|
| Фамилия | Surname | `surname_ru` | Uppercase Cyrillic: ИВАНОВ |
| Имя | First Name | `name_ru` | Uppercase Cyrillic: СЕРГЕЙ |
| Отчество | Patronymic | `patronymic_ru` | Uppercase Cyrillic: ПЕТРОВИЧ |
| Дата рождения | Date of Birth | `dob` | DD.MM.YYYY |
| Пол | Sex | `gender` | M/Ж |
| Гражданство | Nationality | `nationality_ru` | — |
| Номер паспорта | Passport Number | `id_number` | Series: 2+2 digits, Number: 6 digits → `\d{2}\s?\d{2}\s?\d{6}` |
| Кем выдан | Issuing Authority | `authority` | — |
| Дата выдачи | Issue Date | `issue_date` | DD.MM.YYYY |
| Срок действия | Expiry | — | DD.MM.YYYY |

### Name parsing
- Фамилия, Имя, Отчество are **separate fields** — no splitting needed
- All Cyrillic text is **uppercase** (not lowercase as in normal Russian)
- Regex must use `[А-ЯЁ]` for uppercase match

### Date format
- Always DD.MM.YYYY with dots — unambiguous
- Example: 15.05.1985 → [DOB]5

---

## Russia 🇷🇺 — Паспорт РФ (Internal Passport)

**Tesseract language:** `rus+eng`

Same field labels as international passport. Main differences:

| Field | Passport РФ | International |
|---|---|---|
| Title | Паспорт гражданина Российской Федерации | Заграничный паспорт |
| ID format | Серия 40 01 Номер 123456 | Series + number as one block |
| Patronymic | Always present | Present |

ID format: `\d{2}\s?\d{2}\s?\d{6}` (2 digits + space + 2 digits + space + 6 digits)

---

## MRZ (Machine Readable Zone) — ICAO 9303

Present on all modern passports. Two lines of 44 characters each:

```
Line 1: P<UTOSURNAME<<GIVEN<<<<<<<<<<<<<<<<<<<<<<<
Line 2: [DocNumber]<0UTOA1234567890<12345678901234
```

| Position | Line 1 | Meaning |
|---|---|---|
| 0 | P | Document type (P=passport) |
| 1 | < | Issuer (ISO code or <) |
| 2–44 | SURNAME<<GIVEN | Name: surnames up to <<, then given names |

| Position | Line 2 | Meaning |
|---|---|---|
| 0–8 | [DocNumber] | Passport number |
| 9 | < | Check digit |
| 10–13 | UTO | Nationality (ISO) |
| 14–19 | 010129 | DOB (YYMMDD) |
| 20 | 2 | Check digit |
| 21–27 | 1234567 | Sex + expiry (YYMMDD) |
| 28 | 8 | Check digit |
| 29–42 | 12345678901234 | Personal number |
| 43 | 9 | Final check digit |

### MRZ date century heuristics
- YY >= 30 → year 19YY (born before 1930 is rare for active passports)
- YY < 30 → year 20YY
