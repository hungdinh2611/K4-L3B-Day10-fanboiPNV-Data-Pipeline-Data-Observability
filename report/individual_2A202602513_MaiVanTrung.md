# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Mai Văn Trung             |
| MSSV               | 2A202602513                     |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | fanboiPNV     |
| Vai trò chính    | Trưởng nhóm · Pipeline integration & evidence owner                 |
| Repository         | https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Baseline orchestration | `src/pipelines/phase1.py` — `run_phase1_pipeline`, `save_clean_artifacts` | `Settings`, raw records, các module ingestion/retrieval/evaluation/observability | Clean CSV/JSON, collection `papers-baseline`, `baseline_metrics.json`, `phase1_report.md` | Hoàn thành |
| Corruption flow & repair | `src/pipelines/corruption_flow.py` — `run_corruption_flow_pipeline`, `repair_from_raw_snapshot` | Clean data, baseline metrics, `crossref_records.json` | Corrupted/repaired metrics, quality reports, `corruption_report.md` | Hoàn thành |
| Demo UI (bonus B1) | `src/demo_ui/` (`server.py`, `static/`), `script/run_demo_ui.py` | Artifacts trong `data/`, ChromaDB | Dashboard web phong cách Brutalism | Hoàn thành (cần commit trước khi nộp) |

Phần của tôi phụ thuộc trực tiếp vào output của Giáp (raw/clean/corrupted data), Nam (test set), Tú (quality gate, report) và Hưng (index/artifacts). Các module này chỉ được nối với nhau trong 2 pipeline tôi phụ trách.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Merge và tích hợp nhánh của cả nhóm | Tất cả module | Commit `fdb521f`, `d07cec8`; 2 pipeline chạy end-to-end |
| Viết báo cáo nhóm, TEAM.md, kịch bản thuyết trình | Cả nhóm | `report/group_report.md`, `docs/TEAM.md`, `report/presentation_script.md` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Xâu chuỗi 6 bước Phase 1, in log `[phase1] k/6` | `src/pipelines/phase1.py` | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` | `python script/run_phase1.py` |
| Corrupt → evaluate → gate → repair → evaluate → so sánh | `src/pipelines/corruption_flow.py` | `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` | `python script/run_corruption_flow.py` |
| Dashboard chạy pipeline và hỏi RAG trên 3 collection | `src/demo_ui/` | Trang `/`, link `/?ask=eval_009` | `python script/run_demo_ui.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Bảng so sánh 3 trạng thái trên console và trong `data/reports/corruption_report.md`: Hit Rate 1.00 → 0.90 → 1.00, Quality Gate PASS → FAIL → PASS. Bảng này chứng minh cả silent failure lẫn khả năng phục hồi.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Các module chỉ có giá trị khi chạy đúng thứ tự, trên cùng một bộ đường dẫn artifact và cùng một test set. Phần tôi phụ trách bảo đảm ba trạng thái được so sánh công bằng, và bảo đảm việc phục hồi dựa trên nguồn đáng tin cậy.

### Cách triển khai

- **Phase 1:** ingest → clean → lưu CSV/JSON → build index → sinh test set (hoặc đọc lại nếu đã có) → evaluate → gate + freshness → report. Demo agent chỉ chạy khi có LLM thật.
- **Phase 2:**
  - Nếu chưa có baseline thì tự chạy Phase 1 trước.
  - Tiêm lỗi rồi index vào collection riêng `papers-corrupted`, đánh giá trên **cùng** `test_set.json`, sau đó chạy gate.
  - `repair_from_raw_snapshot()` đọc lại `crossref_records.json` và chạy lại đúng `build_clean_dataframe`, nên không vá từng dòng mà dựng lại toàn bộ. Kết quả được index vào `papers-repaired` và đánh giá lại.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | `Settings` từ `load_settings()`; mọi đường dẫn lấy từ `settings.paths` |
| Output                         | Dict `metrics/quality/freshness`, các file trong `data/results`, `data/quality`, `data/reports` |
| Module phụ thuộc             | `ingestion.*`, `retrieval.index`, `evaluation.*`, `observability.*` |
| Module sử dụng output        | `script/run_*.py`, `demo_ui/server.py` |
| Điều kiện lỗi cần xử lý | Thiếu baseline khi chạy Phase 2; LLM không khả dụng (judge fallback); agent demo lỗi (bắt exception, không làm hỏng pipeline) |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** In bảng 3 cột; corrupted thấp hơn baseline; repaired trở về bằng baseline.
- **Kết quả thực tế:** Hit Rate / F1 / Judge Accuracy lần lượt là 1.00 / 0.90 / 1.00; gate PASS / FAIL / PASS. `repair_from_raw_snapshot()` chạy 2 lần cho cùng một DataFrame, và dữ liệu repaired trùng khớp với dữ liệu sạch.
- **Artifact/log:** `data/reports/corruption_report.md`, `data/results/*_metrics.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Chọn cách phục hồi dữ liệu sau khi bị phá.
- **Các phương án đã cân nhắc:**
  - (1) Vá từng lỗi dựa vào corruption log (đảo ngược từng thay đổi).
  - (2) Dedupe và lọc trên chính dữ liệu bẩn.
  - (3) Dựng lại toàn bộ từ raw snapshot.
- **Phương án đã chọn:** (3).
- **Lý do:**
  - (1) phụ thuộc vào việc log đầy đủ; ngoài đời thực không có log của sự cố.
  - (2) không lấy lại được bài đã bị xóa hay summary đã mất.
  - (3) chỉ phụ thuộc vào nguồn đã lưu trước mọi biến đổi, nên có tính idempotent và code đơn giản vì tái dùng đúng hàm cleaning.
- **Bằng chứng quyết định phù hợp:** Dữ liệu repaired có 24 dòng, 6/6 expectations PASS, mọi metric về 1.00 (`repaired_metrics.json`, `repaired_quality_report.json`).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  - Tất cả câu trả lời có `"reasoning": "Fallback heuristic judge used because the LLM evaluator was unavailable."`. Log demo agent: `Error calling model 'gemini-2.5-flash' (NOT_FOUND): 404 NOT_FOUND ... is no longer available to new users`.
  - Sau khi đổi model: `429 RESOURCE_EXHAUSTED ... You exceeded your current quota`.
- **Lệnh hoặc bước tái hiện:** `python script/run_phase1.py` với `LLM_MODEL=gemini-2.5-flash`.
- **Nguyên nhân gốc:** Model mặc định đã bị ngừng. `_judge_answer` nuốt exception rồi chuyển sang heuristic mà không báo gì; client retry mỗi lời gọi 429 nên corruption flow mất khoảng 12 phút.
- **Cách xử lý:**
  - Đổi `LLM_MODEL=gemini-3.8-flash`, sau đó LLM chấm thật 8/10 câu trước khi hết quota.
  - Thêm chế độ judge heuristic (`llm_provider="mock"`) trong demo UI để demo chạy trong khoảng 2 giây.
  - Báo cáo ghi rõ số câu dùng fallback.
- **Cách xác minh sau khi sửa:** `grep -c "Fallback heuristic" data/results/*_answers.json`. Phase 2 qua UI hoàn tất trong 1,7 giây.
- **Điều học được:** Fallback âm thầm cũng là một dạng silent failure. Phải đếm và báo cáo số lần fallback.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:** JSON gốc được lưu nguyên vào `data/raw/`, rồi parse thành `PaperRecord`. Bước clean chuẩn hóa dữ liệu, tính `age_days` và ghép `text_for_embedding`. MiniLM biến mỗi dòng thành vector, lưu vào collection ChromaDB kèm metadata.
2. **Đo chất lượng:** Mỗi câu hỏi có ground-truth DOI. Retrieval tính là hit nếu DOI đó nằm trong top 4. Câu trả lời được so với ground truth bằng Token F1 và judge.
3. **Quality checks và freshness:** Quality checks kiểm tra cấu trúc và nội dung (null, trùng, độ dài). Freshness kiểm tra thời gian: tỉ lệ bài cũ hơn 180 ngày phải ≤ 25%. Dữ liệu có thể đúng cấu trúc mà vẫn lỗi thời.
4. **Cùng test set:** Cả 3 trạng thái dùng chung test set, để chênh lệch metric chỉ đến từ dữ liệu chứ không phải do câu hỏi khác nhau.
5. **Repair thành công khi:** `repaired_quality_report.json` đạt 6/6 và fresh, và `repaired_metrics.json` bằng `baseline_metrics.json`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.00 |       0.90 |      1.00 | Chỉ giảm 1 câu dù 20/24 bài bị phá |
| `mean_token_f1`      |      1.00 |       0.90 |      1.00 | Giảm do 1 câu trả lời rỗng |
| `judge_accuracy`     |      1.00 |       0.90 |      1.00 | Judge heuristic nên bám theo F1 |
| `mean_judge_score`   |      5.00 |       4.60 |      5.00 | Câu sai được 1 điểm |
| Quality checks         |      6/6 |       4/6 |      6/6 | Gate phản ứng mạnh hơn metric |
| Freshness status       |      Fresh 4,2% |       Stale 31,8% |      Fresh 4,2% | Stale date làm vượt ngưỡng 25% |

### Kết luận từ số liệu

1. Blank summary → check `summary ≥ 30` FAIL (4 vi phạm) → `eval_009` trả lời rỗng → F1 và Judge Accuracy còn 0.90.
2. Repair từ raw → 6/6 PASS, fresh → mọi metric về 1.00.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Blank summary, vì nó làm một câu trả lời hỏng hoàn toàn (F1 = 0) và cũng bị gate bắt được. Drop latest làm retrieval miss nhưng gate lại bỏ lọt.

Kết quả nào khác với kỳ vọng ban đầu?

Tôi kỳ vọng metric sẽ giảm mạnh, nhưng chúng chỉ giảm 0.10. Khi kiểm tra `corruption_log.json` đối chiếu với `test_set.json`, tôi thấy 8/10 câu có bài bị phá, nhưng loại lỗi hiếm khi trúng đúng trường được hỏi.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Pipeline cần tính idempotent và một điểm neo raw thì mới phục hồi được một cách tin cậy.
2. Quality Gate phản ứng rõ hơn metric của AI (FAIL so với chỉ −0.10).
3. Dữ liệu hỏng làm RAG sai trong im lặng: không có exception nào.

### Nếu có thêm thời gian

Làm pipeline fail-closed: khi gate FAIL thì không index và tự gọi repair (bonus B2). Đo bằng cách xác nhận collection đang phục vụ vẫn cho Hit Rate 1.00 ngay cả sau khi tiêm lỗi.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Mai Văn Trung
**Ngày xác nhận:** [YYYY-MM-DD]
