# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Hoàng Anh Tú             |
| MSSV               | 2A202602643                     |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | fanboiPNV     |
| Vai trò chính    | Observability & reporting owner                 |
| Repository         | https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Quality Gate GX 1.x | `src/observability/quality.py` — `run_data_quality_checks`, `_run_gx_expectations` | DataFrame của từng trạng thái, `Settings` | `data/quality/<stage>_quality_report.json` | Hoàn thành |
| Freshness SLA | `evaluate_freshness_sla`, `build_freshness_report` | DataFrame (`published`, `age_days`) | `data/quality/*freshness_report.json` | Hoàn thành |
| Reporting | `src/observability/reporting.py` — `generate_phase1_report`, `generate_corruption_report` | Metrics, quality, freshness | `data/reports/phase1_report.md`, `corruption_report.md` | Hoàn thành |

Tôi đưa code lên trong commit `cf91356` từ tài khoản GitHub `ttien0181`. Gate là tín hiệu mà Trung dùng trong corruption flow để kết luận dữ liệu bẩn hay sạch.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Thống nhất tên cột với phần cleaning | Giáp (cleaning) | Gate đọc đúng `paper_id`, `title`, `summary`, `text_for_embedding`, `age_days` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| 4 expectations (6 check) theo GX 1.x Ephemeral Context | `quality.py` | Baseline PASS 6/6 | Lệnh kiểm tra Pha 4 in `Quality check status = True` |
| Freshness SLA | `evaluate_freshness_sla` | Baseline 4,2%, Corrupted 31,8% | `freshness_report.json` |
| Báo cáo markdown 3 trạng thái | `reporting.py` | `corruption_report.md` có bảng delta | Mở file report |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`data/quality/corrupted_quality_report.json`: `success = false`, `expectations_passed = 4/6`, `failed_expectations = [expect_column_values_to_be_unique(paper_id), expect_column_value_lengths_to_be_between(summary)]`, freshness `stale_ratio = 0.3182`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu hỏng không gây exception, nên cần một chốt kiểm tra tự động ở tầng dữ liệu để phát hiện nó trước khi vào vector DB.

### Cách triển khai

- Dùng GX 1.x Ephemeral Context theo chuỗi `get_context(mode="ephemeral")` → `data_sources.add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `get_batch`. Ephemeral Context không tạo project GX trên đĩa.
- Tạo một `ExpectationSuite` gồm:
  - `ExpectTableRowCountToBeBetween(5, 5000)`;
  - `ExpectColumnValuesToNotBeNull` cho 3 cột;
  - `ExpectColumnValuesToBeUnique(paper_id)`;
  - `ExpectColumnValueLengthsToBeBetween(summary, min=30)`.
- Validate cả suite một lần bằng `batch.validate(suite)`.
- Freshness: `stale_ratio = rows(age_days > 180) / total`, và `is_fresh = stale_ratio ≤ 0.25`.
- `success = tất cả expectation PASS AND is_fresh`. Kết quả được ghi JSON có cả `observed_value` và `unexpected_count`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | DataFrame có `paper_id`, `title`, `summary`, `text_for_embedding`, `published`, `age_days`; tên stage |
| Output                         | Dict `{success, expectations_passed/total, failed_expectations, checks[], freshness{...}}` + file JSON |
| Module phụ thuộc             | `great_expectations` 1.18, `core.config` (`freshness_threshold_days`) |
| Module sử dụng output        | `pipelines.phase1`, `pipelines.corruption_flow`, `reporting`, `demo_ui` |
| Điều kiện lỗi cần xử lý | Cột object lẫn kiểu (ép về `str` nhưng giữ null); DataFrame rỗng (`is_fresh = False`); NaN trong kết quả |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Tín hiệu hoàn thành: Quality check status =', res['success'])"
```

- **Kết quả mong đợi:** `Quality check status = True`
- **Kết quả thực tế:** `True`. Thử cố tình làm hỏng từng loại (còn 3 dòng, title null, trùng id, summary 5 ký tự, 40% bài cũ): mỗi trường hợp đều FAIL đúng check tương ứng.
- **Artifact/log:** `data/quality/baseline_quality_report.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Freshness có nên làm gate FAIL hay chỉ là cảnh báo riêng.
- **Các phương án đã cân nhắc:**
  - (1) Freshness chỉ ghi report, không ảnh hưởng `success`.
  - (2) Gộp freshness vào `success` của gate.
- **Phương án đã chọn:** (2).
- **Lý do:** Với RAG về bài báo mới, dữ liệu cũ cũng là lỗi chất lượng: câu hỏi về ngày xuất bản sẽ trả lời sai. Tách riêng sẽ khiến người vận hành chỉ nhìn `success` rồi bỏ qua. Đổi lại, gate có thể FAIL chỉ vì dữ liệu cũ đi theo thời gian; vì vậy report vẫn tách `expectations_success` và `freshness.is_fresh` để biết nguyên nhân.
- **Bằng chứng quyết định phù hợp:** Ở trạng thái corrupted, freshness báo STALE 31,8%, tức lỗi stale date được phát hiện dù không làm sai câu test nào.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Mỗi lần validate, console bị ngập bởi hàng chục dòng `Calculating Metrics:   0%|          | 0/32 [00:00<?, ?it/s]...`, che mất log của pipeline.
- **Lệnh hoặc bước tái hiện:** Chạy lệnh kiểm tra Pha 4.
- **Nguyên nhân gốc:** GX 1.x mặc định bật progress bar (tqdm) cho mỗi lần tính metric.
- **Cách xử lý:** `context.variables.progress_bars = ProgressBarsConfig(globally=False)` ngay sau khi tạo context, và đặt logger `great_expectations` ở mức ERROR.
- **Cách xác minh sau khi sửa:** Chạy lại lệnh kiểm tra, output chỉ còn dòng `Tín hiệu hoàn thành: Quality check status = True`.
- **Điều học được:** Log sạch là một phần của observability: nhiễu làm mất tín hiệu quan trọng.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:** Crossref cho ra raw JSON, được parse và clean, rồi embedding MiniLM đưa vào ChromaDB. Gate của tôi kiểm tra DataFrame ngay trước bước index.
2. **Đo chất lượng:** Ground-truth DOI dùng để tính retrieval hit (top 4). Đáp án chuẩn dùng để tính Token F1 và judge.
3. **Quality checks và freshness:** Quality checks xét từng dòng (null, unique, độ dài) và quy mô bảng. Freshness xét phân bố thời gian của cả bảng, theo tỉ lệ bài cũ.
4. **Cùng test set:** Như vậy chênh lệch metric chỉ đến từ dữ liệu, và có thể đặt cạnh tín hiệu của gate để so sánh.
5. **Repair thành công khi:** `repaired_quality_report.json` có `success = true` (6/6, fresh), và `repaired_metrics.json` bằng baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.00 |       0.90 |      1.00 | Metric chỉ giảm nhẹ |
| `mean_token_f1`      |      1.00 |       0.90 |      1.00 | — |
| `judge_accuracy`     |      1.00 |       0.90 |      1.00 | — |
| `mean_judge_score`   |      5.00 |       4.60 |      5.00 | — |
| Quality checks         |      6/6 |       4/6 |      6/6 | Unique (6 vi phạm) và summary length (4 vi phạm) FAIL |
| Freshness status       |      Fresh 4,2% |       Stale 31,8% |      Fresh 4,2% | 7/22 bài cũ > ngưỡng 25% |

### Kết luận từ số liệu

1. Stale date lùi 6 bài → freshness 31,8% > 25%, trạng thái STALE → không câu test nào sai (các bài đó thuộc câu hỏi summary/authors), nhưng gate vẫn đóng. Đây là trường hợp gate phát hiện sớm hơn metric.
2. Repair → cả 6 check PASS và freshness 4,2% → metric về 1.00.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Về tín hiệu quality là duplicate rows (6 dòng vi phạm unique) và blank summary (4 vi phạm), vì cả hai vi phạm trực tiếp một expectation.

Kết quả nào khác với kỳ vọng ban đầu?

Gate bỏ lọt 3/6 lỗi. Drop latest vẫn còn 22 dòng, nằm trong khoảng 5–5000. Noise vẫn có độ dài ≥ 30. Truncate title không có check độ dài title. Tôi xác nhận điều này bằng bảng check trong `corrupted_quality_report.json`.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Gate phải nằm trước bước index, vì sau khi dữ liệu đã được phục vụ thì lỗi trở nên vô hình.
2. Ngưỡng tuyệt đối (5–5000) không bắt được sự sụt giảm tương đối; cần so sánh với lần chạy trước.
3. Metric của RAG và tín hiệu chất lượng bổ sung cho nhau; không cái nào thay thế được cái nào.

### Nếu có thêm thời gian

Thêm expectation so sánh số dòng với baseline (≥ 90%) và `ExpectColumnValueLengthsToBeBetween(title, min=8)`. Đo bằng cách chạy corruption flow và kỳ vọng số check FAIL tăng từ 2 lên 4.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Hoàng Anh Tú
**Ngày xác nhận:** [YYYY-MM-DD]
