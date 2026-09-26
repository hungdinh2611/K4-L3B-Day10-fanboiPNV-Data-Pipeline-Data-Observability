# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | fanboiPNV    |
| Repository         | https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

### Thành viên và phân công

Phân công được đối chiếu với lịch sử commit trên nhánh `main` (`git log`), cột cuối ghi commit làm bằng chứng.

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Mai Văn Trung | 2A202602513 | Trưởng nhóm · Pipeline integration & evidence owner | `src/pipelines/phase1.py` (`run_phase1_pipeline`), `src/pipelines/corruption_flow.py` (`run_corruption_flow_pipeline`, `repair_from_raw_snapshot`); tích hợp & merge các module; demo UI `src/demo_ui/` + `script/run_demo_ui.py`; kịch bản thuyết trình `report/presentation_script.md` — commit `fdb521f`, `d07cec8` |
| 2 | Đinh Bảo Hưng | 2A202602524 | Embedding/vector index & artifact owner | Chạy pipeline, sinh và quản lý artifacts: ChromaDB `data/chroma/` (3 collection), manifest `data/embeddings/`, `data/eval/`, `data/quality/`, `data/results/`, `data/reports/`; chủ repository — commit `ce49f22` |
| 3 | Ngô Văn Giáp | 2A202602644 | Source, cleaning & corruption owner | `src/ingestion/crossref.py` (fetch/retry/fallback/parse), `src/ingestion/cleaning.py` (`build_clean_dataframe`), `src/ingestion/corruption.py` (`corrupt_clean_dataframe`) — commit `53b5fec` |
| 4 | Hoàng Anh Tú | 2A202602643 | Observability & reporting owner | `src/observability/quality.py` (GX 1.x gate, `evaluate_freshness_sla`), `src/observability/reporting.py` (phase 1 & corruption report) — commit `cf91356` (tài khoản GitHub `ttien0181`) |
| 5 | Nguyễn Thành Nam | 2A202602694 | Evaluation-set owner | `src/evaluation/testset.py` (`build_test_set`, 10 câu / 4 dạng), `data/eval/test_set.json` — commit `7be6a50` |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm hoàn thành toàn bộ 8 pha: ingestion Crossref có retry và fallback offline, cleaning, index ChromaDB bằng `all-MiniLM-L6-v2`, test set 10 câu, Quality Gate Great Expectations 1.x kèm Freshness SLA, bộ 6 kịch bản corruption, repair idempotent và báo cáo so sánh 3 trạng thái. Nhóm làm thêm một dashboard web để demo (bonus B1).

Baseline pipeline tạo đủ artifact: raw response/records, cleaned CSV/JSON (24 dòng), 3 collection ChromaDB, test set, `baseline_metrics.json`, các report chất lượng/freshness và `phase1_report.md`. Baseline đạt Hit Rate 1.00, Token F1 1.00, gate 6/6 PASS, chỉ 4,2% bài cũ.

Corruption tác động tới 20/24 bài báo, nhưng pipeline vẫn chạy mà không phát sinh lỗi (silent failure). Hit Rate và Token F1 chỉ giảm còn 0.90. Hai lỗi thấy rõ nhất là **blank summary** (làm câu `eval_009` trả lời rỗng, gate bắt được qua kiểm tra độ dài summary) và **drop latest** (bài gốc của `eval_004` biến mất, retrieval miss). Quality Gate chuyển sang FAIL: 4/6 expectations đạt, và 31,8% bài đã cũ.

Repair dựng lại dữ liệu từ raw snapshot, cho ra 24 dòng trùng khớp với dữ liệu sạch. Mọi metric về lại 1.00 và gate PASS.

Giới hạn lớn nhất: gate không phát hiện được drop, noise và truncate title. Ngoài ra LLM Judge đang phải chạy heuristic vì Gemini hết quota.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (hoặc snapshot offline data/raw/crossref_response.json)
    -> raw response + raw records (data/raw/)
    -> cleaning và data modeling (data/clean/papers_clean.*)
    -> embedding MiniLM + ChromaDB collection papers-baseline
    -> test set 10 câu (data/eval/test_set.json) -> evaluation baseline
    -> Quality Gate GX 1.x + Freshness SLA (data/quality/)
    -> corruption 6 kịch bản (data/clean/papers_clean_corrupted.*, corruption_log.json)
    -> re-index (papers-corrupted) và re-evaluate trên cùng test set
    -> repair từ raw records (papers-repaired) và re-evaluate
    -> comparison report (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref `/works` hoặc snapshot offline | Offline-first; gọi API khi `REFRESH_SOURCE=1`, retry 3 lần cho 429/5xx, fallback snapshot; parse DOI/title/abstract/author/subject/date, bỏ thẻ JATS | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Ngô Văn Giáp |
| Cleaning          | `crossref_records.json` | Chuẩn hóa khoảng trắng, `paper_id` lowercase, parse ngày, tính `age_days`, bỏ dòng thiếu field bắt buộc, dedupe theo `paper_id`, ghép `text_for_embedding` 5 phần | `data/clean/papers_clean.csv`, `papers_clean.json` | Ngô Văn Giáp |
| Embedding/index   | Clean dataframe | `all-MiniLM-L6-v2` (normalize), ChromaDB cosine, xóa & tạo lại collection mỗi lần build | `data/chroma/`, `data/embeddings/papers_embeddings*.json` | Đinh Bảo Hưng |
| Evaluation        | Clean dataframe | 10 câu trải đều corpus, 4 dạng; đo Hit Rate, Token F1, judge | `data/eval/test_set.json`, `data/results/*_metrics.json`, `*_answers.json` | Nguyễn Thành Nam |
| Observability     | Dataframe mỗi trạng thái | 4 expectations GX 1.x (6 check) + Freshness SLA (`age_days > 180`, ngưỡng 25%) | `data/quality/*_quality_report.json`, `*freshness_report.json`, `data/reports/*.md` | Hoàng Anh Tú |
| Corruption/repair | Clean dataframe / raw records | 6 kịch bản lỗi (seed 42) + log; repair dựng lại từ raw records | `data/clean/papers_clean_corrupted.*`, `papers_clean_repaired.*`, `data/results/corruption_log.json` | Ngô Văn Giáp (corruption), Mai Văn Trung (repair) |
| Orchestration     | Settings `src/core/config.py` | Phase 1: ingest → clean → index → testset → evaluate → gate → report. Phase 2: corrupt → evaluate → gate → repair → evaluate → report | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` | Mai Văn Trung |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `gemini`         |
| `LLM_MODEL`                | `gemini-3.8-flash` (bản `gemini-2.5-flash` mặc định trả 404 — xem mục 11) |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2`         |
| Số lượng Crossref records | 24         |
| Retrieval`top_k`           | 4         |
| Freshness threshold          | `age_days > 180` là bài cũ; `is_fresh = False` khi tỉ lệ bài cũ > 25%         |
| Random seed, nếu có        | 42 (corruption suite)         |

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

Demo UI (tùy chọn, bonus B1):

```bash
uv run python script/run_demo_ui.py
```

> Trên Windows, nếu console báo `UnicodeEncodeError` khi in tiếng Việt, chạy `$env:PYTHONIOENCODING="utf-8"` trước.

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-09-26 11:25 (+07) | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow   | Thành công | 2026-09-26 11:21 (+07) | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` |

Hai lần chạy dùng chế độ judge heuristic (xem mục 11). Mỗi phase mất khoảng 2 giây.

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API `https://api.crossref.org/works`; bài nộp dùng snapshot offline `data/raw/crossref_response.json` |
| Query/filter                | `query=agentic retrieval augmented generation large language model`, `filter=from-pub-date:<run_date − 180 ngày>,has-abstract:true`, `rows=24` |
| Thời điểm lấy dữ liệu | Snapshot có trong repo từ commit `aa10f99` (2026-09-25 23:38 +07); mặc định pipeline không gọi lại API |
| Số record nhận được    | 24 (`total-results` = 24), sau parse còn 24 |
| Cơ chế retry/backoff      | Tối đa 3 lần cho HTTP 429/500/502/503/504 và lỗi mạng, backoff 2s → 4s; hết lượt thì fallback snapshot offline. Nếu API trả về 0 record hợp lệ cũng fallback |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | string | Có | DOI, dùng làm document ID | Thiếu → bỏ record; lowercase; trùng → giữ bản đầu |
| `title` | string | Có | Tiêu đề bài báo | Thiếu → bỏ record; chuẩn hóa khoảng trắng |
| `summary` | string | Có | Abstract đã bỏ thẻ JATS/HTML | Thiếu/rỗng → bỏ record |
| `authors` | list[string] | Không | Danh sách "given family" | Thiếu → `[]`; bỏ tên rỗng, bỏ trùng |
| `categories` | list[string] | Không | Subject Crossref | Thiếu → `[]`; `primary_category` = phần tử đầu |
| `published` | string `YYYY-MM-DD` | Có | Ngày xuất bản (published → print → online → issued) | Không có / không parse được → bỏ record |
| `updated` | string `YYYY-MM-DD` | Không | Ngày cập nhật | Thiếu → dùng `published` |
| `abs_url`, `pdf_url` | string | Không | Link bài báo | Thiếu → `https://doi.org/<DOI>`; `pdf_url` fallback `abs_url` |
| `age_days` | int | Có (clean) | `run_date − published` (ngày) | Tính lại mỗi lần chạy |
| `authors_joined`, `categories_joined`, `summary_chars` | string/int | Có (clean) | Cột phụ cho index và quality check | Sinh từ các cột trên |
| `text_for_embedding` | string | Có (clean) | Văn bản đưa vào embedding | Sinh từ 5 trường |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bỏ thẻ JATS/HTML trong abstract (`<jats:p>`) | Validity | 24 | `crossref_records.json`: không còn ký tự `<` trong `summary` |
| Chuẩn hóa khoảng trắng mọi trường text | Consistency | 0 (snapshot sạch) | Test thủ công: `"  Spaced   Title  "` → `"Spaced Title"` |
| Bỏ record thiếu `paper_id`/`title`/`summary`/ngày hợp lệ | Completeness | 0 (snapshot đủ) | Test thủ công: summary rỗng bị loại (27 → 25 dòng) |
| Dedupe theo `paper_id` | Uniqueness | 0 (snapshot không trùng) | Test thủ công: 1 bản trùng bị loại; GX `ExpectColumnValuesToBeUnique` PASS |
| Tính `age_days`, sắp xếp theo ngày mới nhất | Timeliness | 24 | `age_days` từ 66 đến 182 trong `papers_clean.json` |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

- **Document ID:** DOI của Crossref, lowercase, lưu ở cột `paper_id`. Đây là khóa để dedupe, để làm ground truth của test set và để đối chiếu retrieval hit. Trong ChromaDB, mỗi dòng có `record_id = <paper_id>::<index>`, nên dữ liệu bẩn có dòng trùng vẫn index được.
- **`age_days`:** bằng `(run_date − published)` tính theo ngày, cả hai mốc được chuẩn hóa về 00:00 UTC. Vì vậy `age_days` thay đổi theo ngày chạy.
- **`text_for_embedding`:** ghép 5 dòng `Title / Authors / Published / Categories / Summary`. Nhờ vậy vector mang đủ ngữ cảnh cho cả 4 dạng câu hỏi. Sau khi tiêm lỗi, cột này được tạo lại để lỗi đi thẳng vào embedding.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10                 |
| Các`question_type`                    | `summary` (3), `authors` (3), `date` (2), `categories` (2) |
| Ground-truth document ID                 | `paper_id` (DOI) của bài được chọn; ground truth là câu đầu tiên của summary / `authors_joined` / `published` / `categories_joined` |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2`                  |
| Vector store/collection                  | ChromaDB persistent `data/chroma/`, cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval`top_k`                       | 4                   |
| LLM provider/model                       | `gemini` / `gemini-3.8-flash` cho judge; lần chạy nộp bài dùng judge heuristic (xem mục 11) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha256 `85695f9825f0f740…`) |

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

Test set chỉ được sinh một lần từ dữ liệu sạch. Các lần chạy sau đọc lại đúng file đó, trừ khi đặt `REFRESH_TEST_SET=1`. Hàm `build_test_set` chọn bài theo thứ tự `paper_id` nên có tính tất định: chạy lại cho ra đúng bộ câu cũ. Ba trạng thái dùng cùng câu hỏi, cùng ground truth, cùng model và cùng `top_k`, chỉ khác dữ liệu được index. Nhờ vậy, chênh lệch metric phản ánh đúng tác động của dữ liệu. Nếu sinh test set lại từ dữ liệu bẩn, các câu về bài bị xóa sẽ biến mất và làm che đi thiệt hại.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | 24 items / 24 records |
| Cleaned dataset          | `data/clean/`                        | Có | `papers_clean.csv/json`, 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/`                   | Có | 3 manifest + ChromaDB `data/chroma/`, 24 documents cho baseline |
| Evaluation set           | `data/eval/`                         | Có | `test_set.json`, 10 câu |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Kèm `baseline_answers.json` |
| Quality/freshness        | `data/quality/`                      | Có | `baseline_quality_report.json`, `freshness_report.json` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Bảng source, metrics, 6 check, freshness |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.00 | 10/10 câu có tài liệu ground truth nằm trong top 4  |
| `mean_token_f1`      |     1.00 | Câu trả lời trích đúng trường cần hỏi, khớp hoàn toàn đáp án |
| `judge_accuracy`     |     1.00 | 10/10 đúng; judge heuristic theo Token F1 (≥ 0,5 → đúng) |
| `mean_judge_score`   |     5.00 | Heuristic: F1 ≥ 0,95 → 5 điểm |
| Ragas, nếu có        | N/A | Không bật `RUN_RAGAS=1`: pass Ragas cần LLM, và Gemini đang hết quota |

## 8. Data quality và freshness

### Quality checks

Artifact chung: `data/quality/baseline_quality_report.json`.

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `ExpectTableRowCountToBeBetween` | Volume/Completeness | 5 ≤ rows ≤ 5000 | PASS — 24 dòng | baseline quality report |
| `ExpectColumnValuesToNotBeNull(paper_id)` | Completeness | 0 null | PASS — 0 | baseline quality report |
| `ExpectColumnValuesToNotBeNull(title)` | Completeness | 0 null | PASS — 0 | baseline quality report |
| `ExpectColumnValuesToNotBeNull(text_for_embedding)` | Completeness | 0 null | PASS — 0 | baseline quality report |
| `ExpectColumnValuesToBeUnique(paper_id)` | Uniqueness | 0 trùng | PASS — 0 | baseline quality report |
| `ExpectColumnValueLengthsToBeBetween(summary)` | Validity | ≥ 30 ký tự | PASS — 0 vi phạm | baseline quality report |
| Freshness SLA (`evaluate_freshness_sla`) | Timeliness | ≤ 25% bài có `age_days > 180` | PASS — 1/24 (4,2%) | `data/quality/freshness_report.json` |

Gate dùng Great Expectations 1.x Ephemeral Context (`data_sources.add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `batch.validate(suite)`). `success = True` chỉ khi mọi expectation PASS **và** `is_fresh = True`.

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Cleaned dataset (cột `published` / `age_days`), trước khi index |
| Timestamp mới nhất       | 2026-07-22 (cũ nhất: 2026-03-28)                         |
| Ngưỡng freshness         | Bài cũ nếu `age_days > 180`; `is_fresh = False` khi tỉ lệ bài cũ > 25%                         |
| Trạng thái baseline      | Fresh               |
| Lý do                     | Chỉ 1/24 bài (4,2%) vượt 180 ngày, đó là bài 2026-03-28 với `age_days` = 182 tại ngày chạy 2026-09-26 |

## 9. Corruption scenarios và repair

Cột "Câu test bị ảnh hưởng" là các câu có tài liệu ground truth nằm trong số bài bị phá.

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Drop latest records | Xóa 20% bài có `published` mới nhất | 5 | Mất dữ liệu mới | Gate **không bắt được** (22 dòng vẫn trong khoảng 5–5000). `eval_004` retrieval miss, kéo Hit Rate −0.10; câu trả lời vẫn "đúng" nhờ lấy từ bài khác cùng lĩnh vực | Dựng lại từ raw records |
| Blank summary | Gán `summary = ""` | 3 (+1 bản sao) | `summary ≥ 30` FAIL | FAIL với 4 vi phạm. `eval_009` trả lời rỗng, F1 = 0; `eval_010` (hỏi authors) không bị ảnh hưởng | Dựng lại từ raw records |
| Inject noise | Chèn chuỗi rác + đảo ngược summary | 3 | Độ dài vẫn ≥ 30, gate khó bắt | Gate **không bắt được**. `eval_007` (date) và `eval_008` (categories) vẫn đúng vì không hỏi summary | Dựng lại từ raw records |
| Truncate title | Cắt title còn 7 ký tự | 3 | Không có check độ dài title | Gate **không bắt được**. `eval_002` (authors) vẫn hit nhờ semantic search dù lookup theo title thất bại | Dựng lại từ raw records |
| Stale date | Lùi `published` 365 ngày, tăng `age_days` tương ứng | 6 | Freshness FAIL | STALE: 7/22 = 31,8% > 25%. `eval_005`/`eval_006` hỏi summary/authors nên vẫn đúng | Dựng lại từ raw records |
| Duplicate rows | Nhân đôi dòng | 3 | Unique `paper_id` FAIL | FAIL: 6 dòng trùng `paper_id`. Không làm sai câu nào | Dựng lại từ raw records, dedupe theo `paper_id` |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi đủ 6 loại lỗi với `counts`, `seed = 42`, `input_rows = 24`, `output_rows = 22`, và 23 thay đổi. Mỗi thay đổi có `type`, `paper_id`, giá trị `before` và `after`. Các lỗi 2–5 được tiêm vào những bài khác nhau, nên tổng cộng 5 + 15 = 20/24 bài bị động vào.

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

`repair_from_raw_snapshot()` không sửa từng dòng hỏng. Hàm đọc lại `data/raw/crossref_records.json`, tức bản raw được lưu ở bước ingestion trước mọi biến đổi (lineage anchor), rồi chạy lại đúng hàm `build_clean_dataframe`. Kết quả không phụ thuộc vào trạng thái hỏng nên có tính idempotent: chạy 2 lần cho cùng một DataFrame. Dữ liệu repaired trùng khớp 100% với dữ liệu sạch ở mọi cột, trừ `age_days` vốn tính theo ngày chạy. Sau đó collection `papers-repaired` được xóa và index lại từ đầu, không còn vector cũ sót lại, rồi được đánh giá lại trên cùng test set.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |      1.00 |       0.90 |      1.00 |                      −0.10 |             100% | `eval_004` miss do bài gốc bị drop |
| `mean_token_f1`        |      1.00 |       0.90 |      1.00 |                      −0.10 |             100% | `eval_009` trả lời rỗng do blank summary |
| `judge_accuracy`       |      1.00 |       0.90 |      1.00 |                      −0.10 |             100% | Judge heuristic; cùng câu `eval_009` |
| `mean_judge_score`     |      5.00 |       4.60 |      5.00 |                      −0.40 |             100% | `eval_009` được 1 điểm |
| Quality checks pass/fail |      6/6 |       4/6 |      6/6 |                      −2 |             100% | FAIL: Unique `paper_id`, độ dài summary |
| Freshness status         |      Fresh (4,2%) |       Stale (31,8%) |      Fresh (4,2%) |                      +27,6 điểm % |             100% | Lỗi stale date đẩy tỉ lệ bài cũ vượt 25% |

Các kết luận có quan hệ nhân quả, được hỗ trợ bởi artifacts:

1. **Blank summary** xóa tóm tắt của bài `…3671820` → check `summary ≥ 30 ký tự` FAIL với 4 vi phạm (`corrupted_quality_report.json`) → `eval_009` hỏi đúng summary nên câu trả lời rỗng, Token F1 = 0 → `mean_token_f1` và `judge_accuracy` giảm 1.00 → 0.90 (`corrupted_answers.json`). Retrieval vẫn HIT, nên chỉ nhìn Hit Rate thì không thấy câu này bị hỏng.
2. **Drop latest** xóa bài `…3671808` → không có check nào FAIL, vì 22 dòng vẫn nằm trong khoảng 5–5000 → `eval_004` retrieval miss, `retrieval_hit_rate` còn 0.90. Hệ thống lấy một bài khác cùng lĩnh vực nên câu trả lời vẫn khớp đáp án: câu trả lời đúng nhưng nguồn sai. Đây là silent failure mà gate hiện tại bỏ lọt (xem mục 12).
3. **Repair** dựng lại từ raw records → 6/6 expectations PASS, freshness 4,2% → toàn bộ metric về 1.00 (`repaired_metrics.json`, `repaired_quality_report.json`).

Ghi chú thêm: 8/10 câu test có tài liệu ground truth bị phá, nhưng chỉ 2 câu trả lời sai. Lý do là câu trả lời chỉ hỏng khi loại lỗi trúng đúng trường mà câu hỏi hỏi (blank summary và câu hỏi summary). Metric trên test set vì vậy đánh giá thấp mức thiệt hại, nên cần giám sát ở tầng dữ liệu.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi ghép `evaluate_pipeline` với LLM Judge, cả 10 câu có `judge.reasoning = "Fallback heuristic judge used…"`. Lần chạy corruption flow mất khoảng 12 phút thay vì khoảng 1 phút.
- **Nguyên nhân:** Model mặc định `gemini-2.5-flash` trả `404 NOT_FOUND` (Google đã ngừng cấp cho người dùng mới). Sau khi đổi model, Gemini trả `429 RESOURCE_EXHAUSTED` vì hết quota free tier. `_judge_answer` bắt exception rồi âm thầm chuyển sang heuristic, còn client LangChain retry mỗi lời gọi trước khi bỏ cuộc, nên pipeline rất chậm.
- **Cách xử lý:**
  - Đổi `LLM_MODEL` sang `gemini-3.8-flash`: ở lần chạy lúc 10:02, 8/10 câu được LLM chấm thật trước khi hết quota.
  - Thêm chế độ judge heuristic trong demo UI (dùng `LLM_PROVIDER=mock` khi tắt "LLM judge thật") để demo chạy trong khoảng 2 giây.
  - Báo cáo ghi rõ số câu dùng fallback thay vì ngầm coi là LLM chấm.
- **Cách xác minh:** Đếm số câu fallback bằng `grep -c "Fallback heuristic" data/results/*_answers.json`, kết quả là 10 ở mỗi trạng thái. Hit Rate và Token F1 không phụ thuộc LLM, nên kết luận ở mục 10 vẫn đứng vững.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Gate không bắt drop, noise, truncate title | 3/6 kịch bản lọt qua, trong đó drop gây retrieval miss | Thêm check: số dòng ≥ 90% lần chạy trước, `title` ≥ 8 ký tự, tỉ lệ ký tự không phải chữ trong summary < 10%. Xác minh bằng cách chạy lại corruption flow và kỳ vọng thêm 3 check FAIL |
| Test set 10 câu, loại câu hỏi ít trùng loại lỗi | Metric chỉ giảm 0.10 dù 20/24 bài bị phá | Sinh câu hỏi cho mọi tài liệu × 4 dạng (96 câu). Kỳ vọng chênh lệch metric phản ánh đúng số bài hỏng |
| Judge chạy heuristic do hết quota Gemini | `judge_accuracy` trùng với Token F1, chưa đo được chất lượng ngữ nghĩa | Chạy lại khi còn quota (hoặc dùng provider khác qua `LLM_PROVIDER`), bật `RUN_RAGAS=1`, rồi so sánh với kết quả heuristic |
| Pipeline vẫn index dữ liệu khi gate FAIL (cố ý, để đo tác hại) | Trong production, dữ liệu bẩn sẽ được phục vụ | Fail-closed: gate FAIL thì giữ collection cũ và tự gọi `repair_from_raw_snapshot()` (bonus B2). Kiểm thử bằng cách xác nhận collection đang phục vụ không đổi sau corruption |
| Manifest `data/embeddings/*.json` lưu `persist_path` tuyệt đối (do `LocalEmbeddingIndex.build` của starter) | `LocalEmbeddingIndex.load` trên máy khác trỏ sai thư mục | Lưu đường dẫn tương đối theo `project_dir`, hoặc luôn lấy `settings.paths.chroma_dir` khi load |
| Dữ liệu từ snapshot offline, chưa lấy lại từ API sống | Freshness phụ thuộc ngày chạy, không phản ánh dữ liệu mới | Chạy với `REFRESH_SOURCE=1` định kỳ và lưu snapshot theo timestamp |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế (đối chiếu `git log`).
- [ ] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp. *(Chạy lại `run_phase1.py` rồi `run_corruption_flow.py` ngay trước commit cuối.)*
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh (đã kiểm tra `.env.example` qua toàn bộ lịch sử commit).
