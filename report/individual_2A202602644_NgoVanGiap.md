# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Ngô Văn Giáp             |
| MSSV               | 2A202602644                     |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | fanboiPNV     |
| Vai trò chính    | Source, cleaning & corruption owner                 |
| Repository         | https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Raw ingestion | `src/ingestion/crossref.py` — `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref `/works` hoặc snapshot offline | `data/raw/crossref_response.json`, `crossref_records.json` | Hoàn thành |
| Cleaning | `src/ingestion/cleaning.py` — `build_clean_dataframe`, `build_text_for_embedding` | `list[PaperRecord]`, `run_date` | DataFrame sạch 16 cột | Hoàn thành |
| Corruption suite | `src/ingestion/corruption.py` — `corrupt_clean_dataframe` | Clean DataFrame | DataFrame bẩn + `data/results/corruption_log.json` | Hoàn thành |

Tất cả được đưa lên trong commit `53b5fec`. Schema clean do tôi định nghĩa là contract cho phần index (Hưng), quality (Tú) và test set (Nam).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Cung cấp `build_text_for_embedding` để tái dùng | Trung (repair), corruption | Sau khi tiêm lỗi, `text_for_embedding` được tạo lại đúng mẫu 5 phần |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Parse 24 item Crossref, bỏ thẻ JATS | `crossref.py` | 24 records, khớp 100% với file mẫu | Lệnh kiểm tra Pha 2, `git diff data/raw` rỗng |
| Clean, tính `age_days`, dedupe | `cleaning.py` | 24 dòng, `age_days` từ 66 đến 182 | Lệnh kiểm tra Pha 3 |
| 6 kịch bản lỗi, seed 42 | `corruption.py` | 24 → 22 dòng, 23 thay đổi được ghi log | Lệnh kiểm tra Pha 7 |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/results/corruption_log.json`: `counts = {drop_latest_records: 5, blank_summary: 3, inject_noise: 3, truncate_title: 3, stale_date: 6, duplicate_rows: 3}`. Mỗi thay đổi có `paper_id`, `before` và `after`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần lấy dữ liệu ổn định, không phụ thuộc mạng, và chuẩn hóa thành một schema dùng chung. Sau đó cần mô phỏng các sự cố dữ liệu thực tế, có kiểm soát và tái lập được.

### Cách triển khai

- **Ingestion:**
  - Chạy theo kiểu offline-first: đọc snapshot, chỉ gọi API khi đặt `REFRESH_SOURCE=1`.
  - Gọi API có retry 3 lần (backoff 2s, 4s) với 429/5xx; lỗi thì fallback về snapshot.
  - Parse: DOI viết thường; bỏ thẻ `<jats:*>` bằng regex rồi `html.unescape`; ngày lấy theo thứ tự `published → published-print → published-online → issued`; bỏ record thiếu DOI/title/abstract/ngày.
- **Cleaning:** chuẩn hóa khoảng trắng; tính `age_days = (run_date − published).days`; bỏ dòng thiếu field bắt buộc; `drop_duplicates(paper_id)`; sắp xếp theo ngày mới nhất.
- **Corruption:**
  - Seed cố định 42.
  - Drop 20% bài mới nhất trước. Các lỗi 2–5 được tiêm vào những bài **khác nhau** (dùng tập `touched`), để mỗi lỗi đo được riêng.
  - Duplicate được làm sau cùng.
  - Cuối cùng tạo lại `summary_chars` và `text_for_embedding`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Payload Crossref (`message.items[]`: `DOI`, `title[]`, `abstract`, `author[]`, `subject[]`, `published.date-parts`) |
| Output                         | `PaperRecord` (11 trường) → clean DataFrame 16 cột (thêm `authors_joined`, `categories_joined`, `age_days`, `summary_chars`, `text_for_embedding`) |
| Module phụ thuộc             | `core.config`, `core.utils` |
| Module sử dụng output        | `retrieval.index`, `observability.quality`, `evaluation.testset`, `pipelines.*` |
| Điều kiện lỗi cần xử lý | API 429/503/mất mạng; record thiếu field; ngày không parse được; DOI trùng |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

- **Kết quả mong đợi:** `Đã tải 24 bài báo`
- **Kết quả thực tế:** `Đã tải 24 bài báo`, không còn ký tự `<` trong summary. Khi thử với dữ liệu bẩn (27 bản ghi, gồm 1 bản trùng và 1 summary rỗng), cleaning cho ra 25 dòng.
- **Artifact/log:** `data/raw/crossref_records.json`, `data/clean/papers_clean.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi chạy lab, lấy dữ liệu từ API sống hay từ snapshot.
- **Các phương án đã cân nhắc:**
  - (1) Luôn gọi API, chỉ fallback khi lỗi.
  - (2) Offline-first: dùng snapshot, chỉ gọi API khi có cờ.
- **Phương án đã chọn:** (2).
- **Lý do:** API sống trả về dữ liệu khác nhau theo ngày, vì filter `from-pub-date` thay đổi theo ngày chạy. Như vậy test set và metric không tái lập được, và còn có nguy cơ dính rate limit khi cả lớp gọi cùng lúc. Snapshot đảm bảo mọi thành viên có cùng 24 bài.
- **Bằng chứng quyết định phù hợp:** `crossref_records.json` sinh ra khớp 100% với file mẫu (`git diff` rỗng). Mọi lần chạy đều cho 24 bài.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `UnicodeEncodeError: 'charmap' codec can't encode character 'ệ' in position 6: character maps to <undefined>`
- **Lệnh hoặc bước tái hiện:** Chạy lệnh kiểm tra Pha 2 (có in chuỗi "Tín hiệu hoàn thành") trên terminal Windows.
- **Nguyên nhân gốc:** Console Windows dùng mã hóa cp1252, không encode được ký tự tiếng Việt. Code ingestion không có lỗi.
- **Cách xử lý:** Đặt `PYTHONIOENCODING=utf-8` (`$env:PYTHONIOENCODING="utf-8"` trên PowerShell) trước khi chạy.
- **Cách xác minh sau khi sửa:** Chạy lại lệnh, in ra `Tín hiệu hoàn thành: Đã tải 24 bài báo`.
- **Điều học được:** Phải tách lỗi môi trường khỏi lỗi logic: traceback nằm ở `cp1252.py`, không nằm trong module của mình.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:** Payload Crossref được lưu nguyên, rồi parse thành record. Record được clean và ghép thành đoạn văn 5 phần, sau đó embedding MiniLM và lưu vào ChromaDB.
2. **Đo chất lượng:** Mỗi câu hỏi gắn với một DOI. Top 4 có DOI đó thì là hit. Câu trả lời trích đúng trường thì F1 cao.
3. **Quality checks và freshness:** Quality checks bắt dữ liệu sai hình thức (trùng, rỗng, ngắn). Freshness bắt dữ liệu quá cũ, ví dụ lỗi stale date do tôi tiêm vào.
4. **Cùng test set:** Chỉ khi dùng chung test set thì mới quy được thay đổi metric về đúng các lỗi tôi đã tiêm.
5. **Repair thành công khi:** Dữ liệu repaired dựng từ `crossref_records.json` trùng khớp với dữ liệu sạch, gate 6/6, và metric bằng baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.00 |       0.90 |      1.00 | Do lỗi drop latest |
| `mean_token_f1`      |      1.00 |       0.90 |      1.00 | Do lỗi blank summary |
| `judge_accuracy`     |      1.00 |       0.90 |      1.00 | — |
| `mean_judge_score`   |      5.00 |       4.60 |      5.00 | — |
| Quality checks         |      6/6 |       4/6 |      6/6 | Duplicate và blank summary bị bắt |
| Freshness status       |      Fresh |       Stale |      Fresh | Stale date: 6 bài bị lùi, tổng 7/22 bài cũ |

### Kết luận từ số liệu

1. Duplicate 3 dòng → Unique `paper_id` FAIL với 6 dòng trùng → không làm sai câu nào, nhưng gate đóng.
2. Repair đọc lại raw records → 24 dòng, không trùng → Unique PASS, metric về 1.00.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Blank summary: gate bắt được, và nó làm `eval_009` trả lời rỗng.

Kết quả nào khác với kỳ vọng ban đầu?

Inject noise và truncate title không làm sai câu nào, và gate cũng không bắt được. Đối chiếu log với test set, tôi thấy các bài bị chèn nhiễu là bài của câu hỏi `date`/`categories`, và câu hỏi đó không đọc summary.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Lưu raw nguyên bản trước khi biến đổi là điều kiện để phục hồi được.
2. Mỗi lỗi mô phỏng nên kèm một check tương ứng; noise và truncate hiện chưa có check nào.
3. Tác động lên RAG phụ thuộc vào việc lỗi rơi vào trường nào so với loại câu hỏi.

### Nếu có thêm thời gian

Thêm check `title` ≥ 8 ký tự và check tỉ lệ ký tự không phải chữ trong summary < 10%. Đo bằng cách chạy lại corruption flow và kỳ vọng số expectation FAIL tăng từ 2 lên 4.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngô Văn Giáp
**Ngày xác nhận:** [YYYY-MM-DD]
