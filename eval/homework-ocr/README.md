# 作业照片：首轮 OCR 技术验证材料

已整理 **30 张真实纸面作业 / 练习照片，数学、物理、英语各 10 张**，用于[开发阶段第 1 步](../../docs/06-开发.md)的识别技术验证。收集日期：2026-11-04。

**参考转写已起草、未经人工复核，快速试跑的数字只作方向判断，不能据此声称印刷体 ≥ 95% 或手写 ≥ 85%。** 数学、英语主要是小学练习，物理包含初中内容及学段未确认的样本；首轮排查可用，初中产品的最终技术选型还需补测对应学段、实际手机上传的照片。

## 查看照片

打开 [index.html](index.html)，可按学科、常规 / 困难筛选，点击照片查看完整尺寸。浏览页只读取本地图片，没有远程脚本或统计请求。

| 学科 | 目录 | 数量 | 常规 / 困难 | 内容 |
| --- | --- | ---: | --- | --- |
| 数学 | [images/math/](images/math/) | 10 | 5 / 5 | 比、方程、小数、分数、应用题、表格及手写计算过程 |
| 物理 | [images/physics/](images/physics/) | 10 | 5 / 5 | 测量、电功率、压强、浮力、光学、力学、波形及作图 |
| 英语 | [images/english/](images/english/) | 10 | 5 / 5 | 词汇、翻译、补全对话、阅读、手写完整句子 |

30 张都能看到手写内容；其中 28 张同时包含印刷内容，`physics-01`、`physics-04` 为纯手写纸页。手写内容保留原有拼写 / 计算错误、划改和教师批改，识别时应忠实转写，不能用正确答案替换学生原作答。

常规 / 困难是人工目视分组，不是模型评测结果。困难照片保留来源中真实存在的倾斜、阴影、光照不均、弯页、远拍小字、淡铅笔字及局部模糊，没有人工加噪或生成“坏照片”。15 张困难样本不是 15 张都模糊，具体问题见清单的 `quality_tags` 和 `review_note`。

## 文件与来源

| 文件 | 内容 |
| --- | --- |
| [manifest.jsonl](manifest.jsonl) | 每张照片的稳定编号、路径、尺寸、SHA-256、学科、质量问题、来源和处理记录 |
| [index.html](index.html) | 30 张照片的浏览索引 |
| `source-labels/*.json` | 20 张数学 / 英语照片的原发布版面与题干结构标注；**不是完整手写转写，也未经本项目逐字复核** |
| [materials.py](materials.py) | 校验材料完整性；按清单重新下载缺失素材 |
| [requirements.txt](requirements.txt) | 恢复物理照片时使用的 HEIC 解码与 JPEG 编码依赖；与应用依赖分开 |

数学和英语来自 [ExamOCRBench](https://huggingface.co/datasets/jiangxuhao/ExamOCRBench) 的 `task2/train`，选取第 0–9 行数学和第 131–140 行英语，直接解码发布的图片字节，没有缩放或重新压缩。清单记录了来源版本、行号及匿名样本 ID。原发布方说明其页面保留拍摄、手写、涂改等真实困难条件，并提供公开任务标注。

物理照片通过[物理作业图片索引](https://ecywang.com/pic/物理作业图片/)定位到美篇公开图片 CDN。最终下载的是 900–1778 像素边长的 HEIC 图片，**没有采用索引页的 500 像素缓存缩略图**。只做了 HEIC → JPEG 编码转换及 EXIF 方向应用，未做锐化、美化、去阴影、补字或透视校正。清单保存实际下载地址、原始 HEIC 哈希与交付 JPEG 哈希。该部分无法确认原文章 URL，索引页只是发现来源，不能当成图片的作者或授权方。

照片来自公开来源，未确认对本项目的再分发许可；ExamOCRBench 的[数据说明](https://huggingface.co/datasets/jiangxuhao/ExamOCRBench/blob/main/LICENSE_DATA.txt)也要求发布前核实相关权利。图片及来源标注保留在本地项目中，已通过本目录 `.gitignore` 排除，避免随代码误发布。部分物理照片可能保留纸面的姓名 / 班级笔迹；没有把这些身份信息提取为清单字段。对外发布、展示或用于训练前，应另行核实授权并处理可识别信息。

## 校验与恢复

在项目根目录运行，只需 Python 标准库：

```bash
python3 eval/homework-ocr/materials.py
```

校验照片数量、学科分布、重复哈希、每张照片的文件大小和 SHA-256，以及 20 份来源标注的样本 ID。它不计算识别准确率。

新检出代码后，图片不会随 Git 下载。使用独立环境恢复缺失素材：

```bash
python3.12 -m venv /tmp/tzb-ocr-materials-venv
/tmp/tzb-ocr-materials-venv/bin/python -m pip install -r eval/homework-ocr/requirements.txt
/tmp/tzb-ocr-materials-venv/bin/python eval/homework-ocr/materials.py --fetch
```

恢复依赖上游仍然公开可用。脚本会检查来源字节哈希；上游行号、图片内容或 JPEG 编码结果变化时会报错，不会悄悄换成别的照片。固定来源版本可在 `manifest.jsonl` 中查到。

## 识别测试

2026-11-04 做了一次快速试跑，结果和结论见[开发文档 3.6](../../docs/06-开发.md)。参考转写没有人工复核，数字只作方向判断。

| 文件 | 内容 |
| --- | --- |
| `references/*.json` | 每张照片逐题的参考转写：`printed` 印刷文字、`handwritten` 每块手写作答、`note` 说明和“待核对”；`printed_excluded` 的页不评印刷体，有 `exclude` 题的页不评手写；`status` 为 `draft` 表示未复核。含题目原文，和图片一样不进 Git |
| [prompt.md](prompt.md) | 整页识别的提示词 |
| [run.py](run.py) | 用线上的 `MODEL_VISION` 和图片转码识别 30 张，输出到 `runs/<时间>/`；参考转写未冻结时要加 `--draft` |
| [score.py](score.py) | 计分，印刷体、手写分开，写出 `report.md` |

```bash
docker compose -f deploy/compose.dev.yml run --rm -v "$PWD/eval:/eval" -e PYTHONPATH=/app \
    api python /eval/homework-ocr/run.py --draft
python3 eval/homework-ocr/score.py eval/homework-ocr/runs/<时间>
```

## 正式评测时

1. 先逐图划定评测区域，分别人工转写印刷题干和学生手写作答并复核。来源标注仅作辅助，不能把空的 `ResponseSlot.text` 当成学生没有作答。
2. 看不清的区域明确标成不可辨认，并记录占比；冻结评分区域后再运行模型。不能在看到模型结果后剔除失败样本。教师批改、作图及非文字元素单独记录，避免混入学生答案。
3. 明确“识别率”的计算单位和公式，印刷体、手写体分开统计，并按学科、常规 / 困难分组报告。字符准确率、整题完全正确率和判分准确率不是同一指标。
4. 在相同照片、相同参考转写上比较视觉模型与必要时加入的专门 OCR，再依据印刷体 ≥ 95%、手写 ≥ 85% 的门槛调整识别链路。保留模型版本、提示词和原始输出。

这 30 张是首轮技术验证材料，不替代阶段 7 所需的每科 ≥ 100 道题、标准答案及教师评分的正式评测集。
