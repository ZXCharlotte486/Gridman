"""
PDF 工具集 — 合并、拆分、提取页面

支持：
- 合并多个 PDF 为一个
- 按页码范围拆分 PDF
- 提取指定页面
"""
from pathlib import Path


def merge_pdfs(file_paths: list, output_path: str) -> dict:
    """
    合并多个 PDF 文件为一个。

    Args:
        file_paths: PDF 文件路径列表（按顺序合并）
        output_path: 输出文件路径

    Returns:
        dict: {"status": "success"|"error", "output_file": str, "total_pages": int}
    """
    try:
        import fitz  # pymupdf

        if not file_paths:
            return {"status": "error", "message": "未提供文件路径"}

        # 验证文件
        for fp in file_paths:
            if not Path(fp).exists():
                return {"status": "error", "message": f"文件不存在：{fp}"}

        merged = fitz.open()
        for fp in file_paths:
            doc = fitz.open(fp)
            merged.insert_pdf(doc)
            doc.close()

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        merged.save(str(out))
        total_pages = len(merged)
        merged.close()

        return {
            "status": "success",
            "output_file": str(out),
            "total_pages": total_pages,
            "message": f"已合并 {len(file_paths)} 个文件，共 {total_pages} 页",
        }

    except ImportError:
        return {"status": "error", "message": "pymupdf 未安装，请运行：pip install pymupdf"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def split_pdf(file_path: str, ranges: str, output_dir: str) -> dict:
    """
    按页码范围拆分 PDF。

    Args:
        file_path: 输入 PDF 文件路径
        ranges: 页码范围，逗号分隔。如 "1-5,6-10,11-20" 会拆成 3 个文件
        output_dir: 输出目录

    Returns:
        dict: {"status": "success"|"error", "files": [输出文件列表]}
    """
    try:
        import fitz

        fp = Path(file_path)
        if not fp.exists():
            return {"status": "error", "message": f"文件不存在：{file_path}"}

        doc = fitz.open(str(fp))
        total = len(doc)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 解析页码范围
        output_files = []
        for i, r in enumerate(ranges.split(",")):
            r = r.strip()
            if "-" in r:
                parts = r.split("-")
                start = int(parts[0]) - 1  # 转为 0-indexed
                end = int(parts[1])  # fitz 的 to_page 是 exclusive
            else:
                start = int(r) - 1
                end = int(r)

            # 边界检查
            start = max(0, start)
            end = min(total, end)

            if start >= end:
                continue

            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end - 1)

            out_name = f"{fp.stem}_第{start+1}-{end}页.pdf"
            out_path = out_dir / out_name
            new_doc.save(str(out_path))
            new_doc.close()

            output_files.append({
                "file": str(out_path),
                "pages": f"{start+1}-{end}",
                "page_count": end - start,
            })

        doc.close()

        return {
            "status": "success",
            "files": output_files,
            "message": f"已拆分为 {len(output_files)} 个文件",
        }

    except ImportError:
        return {"status": "error", "message": "pymupdf 未安装，请运行：pip install pymupdf"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def extract_pages(file_path: str, pages: str, output_path: str) -> dict:
    """
    从 PDF 中提取指定页面。

    Args:
        file_path: 输入 PDF 文件路径
        pages: 页码，逗号分隔。如 "1,3,5,7-10"
        output_path: 输出文件路径

    Returns:
        dict: {"status": "success"|"error", "output_file": str, "extracted_pages": int}
    """
    try:
        import fitz

        fp = Path(file_path)
        if not fp.exists():
            return {"status": "error", "message": f"文件不存在：{file_path}"}

        doc = fitz.open(str(fp))
        total = len(doc)

        # 解析页码列表
        page_list = []
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                s, e = part.split("-")
                page_list.extend(range(int(s) - 1, int(e)))
            else:
                page_list.append(int(part) - 1)

        # 去重排序，边界检查
        page_list = sorted(set(p for p in page_list if 0 <= p < total))

        if not page_list:
            return {"status": "error", "message": "未指定有效页码"}

        new_doc = fitz.open()
        for p in page_list:
            new_doc.insert_pdf(doc, from_page=p, to_page=p)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        new_doc.save(str(out))
        new_doc.close()
        doc.close()

        return {
            "status": "success",
            "output_file": str(out),
            "extracted_pages": len(page_list),
            "message": f"已提取 {len(page_list)} 页",
        }

    except ImportError:
        return {"status": "error", "message": "pymupdf 未安装，请运行：pip install pymupdf"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
