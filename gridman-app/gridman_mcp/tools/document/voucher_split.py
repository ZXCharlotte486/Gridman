"""
记账凭证 PDF 拆分工具

将一个包含多份记账凭证的扫描 PDF，按凭证自动识别拆分为独立 PDF 文件。
命名格式：记{月份}-{编号}.pdf（如 记11-86.pdf）

原理：识别每页中的"记账凭证"字样或凭证编号模式，确定凭证边界后拆分。
"""
import re
from pathlib import Path


def split_vouchers(
    file_path: str,
    output_dir: str,
    prefix: str = "记",
) -> dict:
    """
    将包含多份记账凭证的 PDF 按凭证拆分。

    Args:
        file_path: 输入 PDF 文件路径（扫描版或数字版）
        output_dir: 输出目录
        prefix: 文件名前缀，默认"记"

    Returns:
        dict: {
            "status": "success"|"error",
            "files": [拆分后的文件列表],
            "total_vouchers": int,
            "message": str
        }
    """
    try:
        import fitz  # pymupdf

        fp = Path(file_path)
        if not fp.exists():
            return {"status": "error", "message": f"文件不存在：{file_path}"}

        doc = fitz.open(str(fp))
        total_pages = len(doc)

        if total_pages == 0:
            return {"status": "error", "message": "PDF 文件为空"}

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── 第一步：提取每页文本，识别凭证边界 ──
        # 凭证编号模式：记-XX、记XX-XX、第XX号、凭证号：XX 等
        voucher_pattern = re.compile(
            r'(?:记[账帐]凭证|记[  ]*(\d{1,2})[  ]*[-—]\s*(\d{1,4}))'
            r'|(?:凭证[号编][：:]?\s*(\d{1,4}))'
            r'|(?:第\s*(\d{1,4})\s*号)'
            r'|(?:记\s*(\d{1,2})\s*[-—]\s*(\d{1,4}))',
            re.IGNORECASE
        )

        # 记账凭证标题模式（用于识别新凭证的起始页）
        title_pattern = re.compile(r'记[账帐]凭证|记帐凭证|会计凭证', re.IGNORECASE)

        page_info = []
        for i in range(total_pages):
            page = doc[i]
            text = page.get_text("text")
            
            # 检查是否是凭证首页
            has_title = bool(title_pattern.search(text))
            
            # 尝试提取凭证编号
            match = voucher_pattern.search(text)
            voucher_id = None
            if match:
                groups = match.groups()
                # 尝试从各个捕获组提取月份和编号
                for j in range(0, len(groups), 2):
                    if groups[j] and j + 1 < len(groups) and groups[j + 1]:
                        voucher_id = f"{prefix}{groups[j]}-{groups[j+1]}"
                        break
                if not voucher_id:
                    for g in groups:
                        if g:
                            voucher_id = f"{prefix}{g}"
                            break

            page_info.append({
                "page": i,
                "has_title": has_title,
                "voucher_id": voucher_id,
                "text_length": len(text),
            })

        # ── 第二步：确定凭证边界 ──
        # 策略：有凭证标题的页面视为新凭证的起始
        boundaries = []
        current_start = 0
        current_id = page_info[0].get("voucher_id") or f"{prefix}001"

        for i in range(1, total_pages):
            if page_info[i]["has_title"]:
                # 当前页是新凭证的开始
                boundaries.append({
                    "start": current_start,
                    "end": i - 1,
                    "voucher_id": current_id,
                })
                current_start = i
                current_id = page_info[i].get("voucher_id") or f"{prefix}{len(boundaries)+1:03d}"

        # 最后一份凭证
        boundaries.append({
            "start": current_start,
            "end": total_pages - 1,
            "voucher_id": current_id,
        })

        # 如果只识别出一份凭证且等于总页数，可能是识别失败
        if len(boundaries) == 1 and total_pages > 2:
            # 退回到按页拆分模式，每页一个文件
            boundaries = []
            for i in range(total_pages):
                vid = page_info[i].get("voucher_id") or f"{prefix}{i+1:03d}"
                boundaries.append({"start": i, "end": i, "voucher_id": vid})

        # ── 第三步：拆分并保存 ──
        output_files = []
        used_names = set()

        for b in boundaries:
            # 处理重名
            name = b["voucher_id"]
            if name in used_names:
                suffix = 2
                while f"{name}_{suffix}" in used_names:
                    suffix += 1
                name = f"{name}_{suffix}"
            used_names.add(name)

            # 拆分
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=b["start"], to_page=b["end"])

            out_path = out_dir / f"{name}.pdf"
            new_doc.save(str(out_path))
            new_doc.close()

            output_files.append({
                "file": str(out_path),
                "voucher_id": name,
                "pages": f"{b['start']+1}-{b['end']+1}",
                "page_count": b["end"] - b["start"] + 1,
            })

        doc.close()

        return {
            "status": "success",
            "files": output_files,
            "total_vouchers": len(output_files),
            "message": f"已拆分为 {len(output_files)} 份凭证（共 {total_pages} 页）",
        }

    except ImportError:
        return {"status": "error", "message": "pymupdf 未安装，请运行：pip install pymupdf"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
