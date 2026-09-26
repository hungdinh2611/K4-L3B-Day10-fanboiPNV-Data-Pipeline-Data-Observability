# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Thành Nam             |
| MSSV               | 2A202602694                     |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | fanboiPNV     |
| Vai trò chính    | Evaluation-set owner                 |
| Repository         | https://github.com/hungdinh2611/K4-L3B-Day10-fanboiPNV-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Benchmark test set | `src/evaluation/testset.py` — `build_test_set` | Clean DataFrame | `data/eval/test_set.json` (10 câu) | Hoàn thành |

Tôi đưa code lên trong commit `7be6a50`. Test set là thước đo chung cho cả 3 trạng thái. `evaluation/metrics.py` (starter) đọc file này để tính Hit Rate, Token F1 và judge.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Đối chiếu câu hỏi với logic trích câu trả lời | `retrieval/qa.py` (starter) | Câu hỏi authors/date/categories được trả lời đúng trường |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Sinh 10 câu, 4 dạng | `testset.py` | summary 3 · authors 3 · date 2 · categories 2 | Lệnh kiểm tra Pha 5 |
| Ground truth gắn DOI | `ground_truth_doc_ids` | 10 DOI khác nhau, đều có trong dữ liệu sạch | Đối chiếu với `papers_clean.json` |
| Test set tất định | `build_test_set` | Chạy lại cho ra cùng file (sha256 `85695f9825f0f740…`) | So sánh 2 lần chạy |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Câu `eval_009` (summary) là câu phát hiện ra silent failure. Ở trạng thái corrupted, retrieval vẫn HIT nhưng câu trả lời rỗng (F1 = 0). Nếu test set không có dạng câu hỏi summary thì lỗi blank summary sẽ không hiện ra trên metric.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Cần một thước đo cố định, có đáp án chuẩn và ID tài liệu, để so sánh hiệu năng RAG giữa dữ liệu sạch, dữ liệu bẩn và dữ liệu đã phục hồi.

### Cách triển khai

- Bỏ các dòng thiếu `paper_id`/`title`/`summary`, dedupe, rồi kiểm tra còn ít nhất 5 tài liệu.
- Sắp xếp theo `paper_id` rồi chọn 10 bài cách đều nhau (`step = n/10`), để phủ cả bài mới lẫn bài cũ và có tính tất định.
- Gán dạng câu hỏi xoay vòng theo thứ tự summary, authors, date, categories.
- Mẫu câu hỏi dùng đúng các cụm "Who authored", "When was", "What categories" mà `qa._extract_answer` nhận diện, và bọc title trong dấu `'...'` để `qa` tra cứu chính xác được.
- Ground truth: câu đầu của summary, `authors_joined`, `published`, `categories_joined`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Clean DataFrame (`paper_id`, `title`, `summary`, `authors_joined`, `published`, `categories_joined`) |
| Output                         | List `{id, question_type, question, ground_truth, ground_truth_doc_ids}` + `data/eval/test_set.json` |
| Module phụ thuộc             | `ingestion.cleaning` (schema), `core.utils.first_sentence` |
| Module sử dụng output        | `evaluation.metrics.evaluate_pipeline`, `pipelines.*`, `demo_ui` |
| Điều kiện lỗi cần xử lý | Ít hơn 5 tài liệu; summary rỗng; trùng `paper_id` |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

- **Kết quả mong đợi:** `Sinh được 10 câu hỏi test`
- **Kết quả thực tế:** `Sinh được 10 câu hỏi test`. Đủ 5 trường, 10 DOI khác nhau và hợp lệ, chạy lại cho kết quả giống hệt.
- **Artifact/log:** `data/eval/test_set.json`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cách chọn bài đưa vào test set.
- **Các phương án đã cân nhắc:**
  - (1) Chọn ngẫu nhiên (`sample`).
  - (2) Lấy 10 bài mới nhất.
  - (3) Chọn cách đều theo `paper_id`.
- **Phương án đã chọn:** (3).
- **Lý do:**
  - (1) chỉ tất định khi cố định seed, và dễ lệch nếu dữ liệu đổi thứ tự.
  - (2) tập trung toàn bộ vào nhóm bài bị lỗi drop latest làm mất, khiến metric sụp đổ một cách giả tạo và không phản ánh các lỗi khác.
  - (3) phủ đều corpus và cho cùng kết quả mỗi lần.
- **Bằng chứng quyết định phù hợp:** Test set chạm vào cả 6 loại lỗi (8/10 câu có tài liệu bị phá), và kết quả tái lập được giữa các lần chạy (cùng sha256).

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ValueError: Need at least 5 clean documents to build a test set, got 3.`
- **Lệnh hoặc bước tái hiện:** `build_test_set(df.head(3), 'x.json')`, mô phỏng trường hợp dữ liệu sạch bị hụt nghiêm trọng.
- **Nguyên nhân gốc:** Khi dữ liệu quá ít, phép chia `step = n/10` sẽ chọn trùng bài, sinh ra test set trùng lặp và vô nghĩa, nhưng không có lỗi nào báo ra.
- **Cách xử lý:** Kiểm tra số tài liệu tối thiểu (`MIN_DOCUMENTS = 5`, khớp ngưỡng row count của gate) và báo lỗi rõ ràng thay vì âm thầm sinh test set xấu.
- **Cách xác minh sau khi sửa:** Chạy lệnh trên, nhận `ValueError` với thông điệp rõ ràng. Với 24 dòng, test set vẫn sinh đủ 10 câu.
- **Điều học được:** Thành phần đo lường cũng có thể gây silent failure; nên fail-fast.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:** Bài báo từ Crossref được lưu raw, clean, ghép `text_for_embedding`, embedding bằng MiniLM rồi lưu vào ChromaDB.
2. **Đo chất lượng:** Mỗi câu hỏi có DOI chuẩn. Nếu DOI đó nằm trong top 4 kết quả thì tính là hit (retrieval quality). Câu trả lời so với ground truth bằng Token F1 và judge (answer quality).
3. **Quality checks và freshness:** Quality checks xét tính hợp lệ của từng dòng và cả bảng. Freshness xét dữ liệu còn mới hay không, qua `age_days`.
4. **Cùng test set:** Test set chỉ sinh một lần từ dữ liệu sạch. Nếu sinh lại từ dữ liệu bẩn, các câu về bài đã bị xóa sẽ biến mất và che đi thiệt hại.
5. **Repair thành công khi:** Trên cùng `test_set.json`, `repaired_metrics.json` bằng `baseline_metrics.json`, và gate PASS.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.00 |       0.90 |      1.00 | `eval_004` (categories) miss |
| `mean_token_f1`      |      1.00 |       0.90 |      1.00 | `eval_009` (summary) F1 = 0 |
| `judge_accuracy`     |      1.00 |       0.90 |      1.00 | — |
| `mean_judge_score`   |      5.00 |       4.60 |      5.00 | — |
| Quality checks         |      6/6 |       4/6 |      6/6 | — |
| Freshness status       |      Fresh |       Stale |      Fresh | — |

### Kết luận từ số liệu

1. Blank summary rơi vào tài liệu của `eval_009` (dạng summary) → gate FAIL ở check summary → F1 của câu này bằng 0, F1 trung bình còn 0.90.
2. Repair → cùng test set cho kết quả 10/10 đúng như baseline.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Blank summary, vì nó trùng đúng loại câu hỏi. Lỗi này cũng rơi vào `eval_010` nhưng câu đó hỏi authors, nên vẫn đúng.

Kết quả nào khác với kỳ vọng ban đầu?

8/10 câu có tài liệu bị phá, nhưng chỉ 2 câu sai. Khi đối chiếu `corruption_log.json` với test set, tôi thấy câu trả lời chỉ sai khi lỗi rơi đúng vào trường được hỏi. Ví dụ `eval_005` hỏi summary nhưng bài chỉ bị lùi ngày, và `eval_007` hỏi ngày nhưng bài bị chèn nhiễu vào summary.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Test set phải cố định và tất định thì mới so sánh được giữa các lần chạy.
2. Metric trên test set đánh giá thấp mức thiệt hại, nên cần giám sát cả ở tầng dữ liệu.
3. Loại câu hỏi quyết định lỗi dữ liệu nào hiện ra trên metric.

### Nếu có thêm thời gian

Sinh câu hỏi cho mọi tài liệu × 4 dạng (96 câu), để mỗi lỗi đều có câu hỏi đúng loại. Đo bằng cách chạy corruption flow và kỳ vọng mức giảm của metric tương ứng với 20/24 bài bị phá.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Thành Nam
**Ngày xác nhận:** [YYYY-MM-DD]
