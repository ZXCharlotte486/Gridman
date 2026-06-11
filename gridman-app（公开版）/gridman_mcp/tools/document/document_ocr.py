"""
文档 OCR 识别工具 — MinerU 云端精准解析

调用 MinerU 云端精准解析 API（vlm 模型），适合复杂排版 PDF（年报、招股书、研究报告）。
支持格式：PDF、图片（png/jpg/jpeg/webp/bmp/tiff）、Word、Excel、PPT。

使用前需配置环境变量 MINERU_API_TOKEN（免费注册 https://mineru.net 获取）。
每个账号每天 1000 页免费额度。
"""
import os
import time
from pathlib import Path

# MinerU 云端 API 配置
_MINERU_API_BASE = "https://mineru.net/api/v4"
_MINERU_POLL_INTERVAL = 3  # 轮询间隔（秒）
_MINERU_POLL_TIMEOUT = 300  # 最大等待时间（秒）

# 支持的文件格式
_SUPPORTED_FORMATS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".jp2", ".webp", ".gif", ".bmp",
    ".tiff", ".tif", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
}


def convert_document(
    file_path: str,
    output_path: str = None,
    langs: str = "zh,en",
) -> dict:
    """
    将文档转换为 Markdown 文本（调用 MinerU 云端精准解析 API）。

    Args:
        file_path: 输入文件路径
        output_path: 输出 Markdown 文件路径（可选）
        langs: 识别语言，默认 "zh,en"

    Returns:
        dict: {
            "status": "success" | "error",
            "text": Markdown 文本,
            "engine": "MinerU API (vlm)",
            "output_file": 输出文件路径（如有）,
            "message": 错误信息（如有）
        }
    """
    import requests
    import zipfile
    import io

    file_path = Path(file_path)

    if not file_path.exists():
        return {"status": "error", "message": f"文件不存在：{file_path}"}

    suffix = file_path.suffix.lower()
    if suffix not in _SUPPORTED_FORMATS:
        return {
            "status": "error",
            "message": f"不支持的格式：{suffix}，支持：{', '.join(sorted(_SUPPORTED_FORMATS))}",
        }

    # 检查 Token
    token = os.environ.get("MINERU_API_TOKEN", "").strip()
    if not token:
        return {
            "status": "error",
            "engine": "MinerU API",
            "message": (
                "未配置 MINERU_API_TOKEN。获取方式：\n"
                "1. 打开 https://mineru.net 并登录\n"
                "2. 点顶部导航栏的【API】\n"
                "3. 左侧边栏 → 智能解析 → 【API 管理】（在'API 文档'下面）\n"
                "4. 点【+ 创建 Token】，复制生成的 Token\n"
                "5. 填入 MCP 配置的 env 中：MINERU_API_TOKEN\n"
                "免费注册，每个账号每天 1000 页免费额度，Token 有效期 90 天。"
            ),
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # 语言映射
    lang_map = {"zh": "ch", "en": "en", "ja": "ja", "ko": "ko"}
    first_lang = langs.split(",")[0].strip()
    mineru_lang = lang_map.get(first_lang, "ch")

    try:
        # ── 步骤 1：申请上传链接 ──
        batch_url = f"{_MINERU_API_BASE}/file-urls/batch"
        batch_data = {
            "files": [{"name": file_path.name}],
            "model_version": "vlm",
            "enable_table": True,
            "enable_formula": True,
            "language": mineru_lang,
        }

        resp = requests.post(batch_url, headers=headers, json=batch_data, timeout=30)
        resp.raise_for_status()
        batch_result = resp.json()

        if batch_result.get("code") != 0:
            msg = batch_result.get("msg", "未知错误")
            err_code = str(batch_result.get("code", ""))
            # Token 错误或过期
            if err_code in ("A0202", "A0211"):
                return {
                    "status": "error",
                    "engine": "MinerU API",
                    "message": (
                        f"Token 无效或已过期（错误码：{err_code}）。\n"
                        "MinerU Token 有效期为 90 天，过期后需重新创建。\n"
                        "操作路径：https://mineru.net → 登录 → 顶部【API】→ 左侧边栏【API 管理】→ 创建新 Token\n"
                        "然后更新 MCP 配置中的 MINERU_API_TOKEN。"
                    ),
                }
            # 文件/额度限制
            limit_messages = {
                "-60005": "文件大小超出限制（最大 200MB）。请压缩文件或拆分后重试。",
                "-60006": "文件页数超出限制（最大 600 页）。请拆分文件后重试。",
                "-60018": "今日解析任务数量已达上限（每天 5000 份文件）。明天再试，或换一个 MinerU 账号。",
                "-60009": "MinerU 服务器任务队列已满，请稍后重试。",
            }
            if err_code in limit_messages:
                return {
                    "status": "error",
                    "engine": "MinerU API",
                    "message": limit_messages[err_code],
                }
            return {
                "status": "error",
                "engine": "MinerU API",
                "message": f"申请上传链接失败：{msg}",
            }

        batch_id = batch_result["data"]["batch_id"]
        file_urls = batch_result["data"]["file_urls"]

        if not file_urls:
            return {"status": "error", "engine": "MinerU API", "message": "未获取到上传链接"}

        # ── 步骤 2：PUT 上传文件 ──
        upload_url = file_urls[0]
        with open(file_path, "rb") as f:
            put_resp = requests.put(upload_url, data=f, timeout=120)

        if put_resp.status_code != 200:
            return {
                "status": "error",
                "engine": "MinerU API",
                "message": f"文件上传失败，HTTP {put_resp.status_code}",
            }

        # ── 步骤 3：轮询解析结果 ──
        result_url = f"{_MINERU_API_BASE}/extract-results/batch/{batch_id}"
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > _MINERU_POLL_TIMEOUT:
                return {
                    "status": "error",
                    "engine": "MinerU API",
                    "message": f"解析超时（等待 {_MINERU_POLL_TIMEOUT} 秒），请稍后重试",
                }

            time.sleep(_MINERU_POLL_INTERVAL)

            poll_resp = requests.get(result_url, headers=headers, timeout=30)
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()

            if poll_data.get("code") != 0:
                return {
                    "status": "error",
                    "engine": "MinerU API",
                    "message": f"查询结果失败：{poll_data.get('msg', '未知错误')}",
                }

            results = poll_data["data"].get("extract_result", [])
            if not results:
                continue

            item = results[0]
            state = item.get("state", "")

            if state == "done":
                zip_url = item.get("full_zip_url", "")
                if not zip_url:
                    return {"status": "error", "engine": "MinerU API", "message": "解析完成但未返回结果链接"}
                break
            elif state == "failed":
                err_msg = item.get("err_msg", "未知错误")
                return {"status": "error", "engine": "MinerU API", "message": f"解析失败：{err_msg}"}
            # pending / running / converting → 继续轮询

        # ── 步骤 4：下载 ZIP 并提取 Markdown ──
        zip_resp = requests.get(zip_url, timeout=120)
        zip_resp.raise_for_status()

        text_parts = []
        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
            md_files = [n for n in zf.namelist() if n.endswith(".md")]
            full_md = [n for n in md_files if n.endswith("full.md")]
            target_files = full_md if full_md else sorted(md_files)

            for md_name in target_files:
                content = zf.read(md_name).decode("utf-8")
                if content.strip():
                    text_parts.append(content)

        if not text_parts:
            return {"status": "error", "engine": "MinerU API", "message": "ZIP 包中未找到 Markdown 内容"}

        text = "\n\n".join(text_parts)

        # 保存到文件
        output_file = None
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            output_file = str(out)

        return {
            "status": "success",
            "engine": "MinerU API (vlm)",
            "text": text,
            "output_file": output_file,
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "engine": "MinerU API", "message": "网络请求超时，请检查网络连接"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "engine": "MinerU API", "message": "无法连接 MinerU 服务器，请检查网络"}
    except Exception as e:
        return {"status": "error", "engine": "MinerU API", "message": str(e)}


def convert_documents_batch(
    file_paths: list,
    output_dir: str = None,
    langs: str = "zh,en",
) -> dict:
    """
    批量将文档转换为 Markdown 文本（调用 MinerU 云端精准解析 API）。

    Args:
        file_paths: 输入文件路径列表（最多 50 个）
        output_dir: 输出目录路径（可选，每个文件生成同名 .md）
        langs: 识别语言，默认 "zh,en"

    Returns:
        dict: {
            "status": "success" | "partial" | "error",
            "results": [每个文件的结果],
            "summary": "成功 X 个，失败 Y 个"
        }
    """
    import requests
    import zipfile
    import io

    if not file_paths:
        return {"status": "error", "message": "未提供文件路径"}

    if len(file_paths) > 200:
        return {"status": "error", "message": f"单次最多 200 个文件，当前 {len(file_paths)} 个。请分批处理。"}

    # 验证所有文件
    valid_files = []
    results = []
    for fp in file_paths:
        p = Path(fp)
        if not p.exists():
            results.append({"file": fp, "status": "error", "message": f"文件不存在：{fp}"})
            continue
        suffix = p.suffix.lower()
        if suffix not in _SUPPORTED_FORMATS:
            results.append({"file": fp, "status": "error", "message": f"不支持的格式：{suffix}"})
            continue
        valid_files.append(p)

    if not valid_files:
        return {"status": "error", "message": "没有有效文件可处理", "results": results}

    # 检查 Token
    token = os.environ.get("MINERU_API_TOKEN", "").strip()
    if not token:
        return {
            "status": "error",
            "engine": "MinerU API",
            "message": (
                "未配置 MINERU_API_TOKEN。获取方式：\n"
                "1. 打开 https://mineru.net 并登录\n"
                "2. 点顶部导航栏的【API】\n"
                "3. 左侧边栏 → 智能解析 → 【API 管理】（在'API 文档'下面）\n"
                "4. 点【+ 创建 Token】，复制生成的 Token\n"
                "5. 填入 MCP 配置的 env 中：MINERU_API_TOKEN\n"
                "免费注册，每个账号每天 1000 页免费额度，Token 有效期 90 天。"
            ),
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    lang_map = {"zh": "ch", "en": "en", "ja": "ja", "ko": "ko"}
    first_lang = langs.split(",")[0].strip()
    mineru_lang = lang_map.get(first_lang, "ch")

    try:
        # 按 50 个一批分组（MinerU 单次申请上传链接上限 50）
        batch_size = 50
        chunks = [valid_files[i:i + batch_size] for i in range(0, len(valid_files), batch_size)]

        for chunk in chunks:
            # ── 步骤 1：批量申请上传链接 ──
            batch_url = f"{_MINERU_API_BASE}/file-urls/batch"
            batch_data = {
                "files": [{"name": p.name} for p in chunk],
                "model_version": "vlm",
                "enable_table": True,
                "enable_formula": True,
                "language": mineru_lang,
            }

            resp = requests.post(batch_url, headers=headers, json=batch_data, timeout=30)
            resp.raise_for_status()
            batch_result = resp.json()

            if batch_result.get("code") != 0:
                msg = batch_result.get("msg", "未知错误")
                err_code = str(batch_result.get("code", ""))
                if err_code in ("A0202", "A0211"):
                    return {
                        "status": "error",
                        "engine": "MinerU API",
                        "message": (
                            f"Token 无效或已过期（错误码：{err_code}）。\n"
                            "操作路径：https://mineru.net → 登录 → 顶部【API】→ 左侧边栏【API 管理】→ 创建新 Token"
                        ),
                    }
                # 对当前批次所有文件标记失败，继续下一批
                for fp in chunk:
                    results.append({"file": str(fp), "status": "error", "message": f"批量申请失败：{msg}"})
                continue

            batch_id = batch_result["data"]["batch_id"]
            file_urls = batch_result["data"]["file_urls"]

            if len(file_urls) != len(chunk):
                for fp in chunk:
                    results.append({"file": str(fp), "status": "error", "message": "上传链接数量与文件数量不匹配"})
                continue

            # ── 步骤 2：逐个 PUT 上传文件 ──
            upload_failed = set()
            for i, (fp, upload_url) in enumerate(zip(chunk, file_urls)):
                try:
                    with open(fp, "rb") as f:
                        put_resp = requests.put(upload_url, data=f, timeout=120)
                    if put_resp.status_code != 200:
                        results.append({"file": str(fp), "status": "error", "message": f"上传失败，HTTP {put_resp.status_code}"})
                        upload_failed.add(i)
                except Exception as e:
                    results.append({"file": str(fp), "status": "error", "message": f"上传异常：{e}"})
                    upload_failed.add(i)

            # ── 步骤 3：轮询批量解析结果 ──
            result_url = f"{_MINERU_API_BASE}/extract-results/batch/{batch_id}"
            start_time = time.time()

            while True:
                elapsed = time.time() - start_time
                if elapsed > _MINERU_POLL_TIMEOUT:
                    # 超时，标记未完成的文件
                    for fp in chunk:
                        if str(fp) not in [r.get("file") for r in results]:
                            results.append({"file": str(fp), "status": "error", "message": "解析超时"})
                    break

                time.sleep(_MINERU_POLL_INTERVAL)

                poll_resp = requests.get(result_url, headers=headers, timeout=30)
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()

                if poll_data.get("code") != 0:
                    for fp in chunk:
                        if str(fp) not in [r.get("file") for r in results]:
                            results.append({"file": str(fp), "status": "error", "message": f"查询失败：{poll_data.get('msg')}"})
                    break

                extract_results = poll_data["data"].get("extract_result", [])
                if not extract_results:
                    continue

                all_done = all(
                    item.get("state") in ("done", "failed")
                    for item in extract_results
                )
                if not all_done:
                    continue

                # ── 步骤 4：下载结果 ──
                for item in extract_results:
                    file_name = item.get("file_name", "unknown")
                    state = item.get("state", "")

                    if state == "failed":
                        results.append({
                            "file": file_name,
                            "status": "error",
                            "message": item.get("err_msg", "解析失败"),
                        })
                        continue

                    zip_url = item.get("full_zip_url", "")
                    if not zip_url:
                        results.append({"file": file_name, "status": "error", "message": "未返回结果链接"})
                        continue

                    try:
                        zip_resp = requests.get(zip_url, timeout=120)
                        zip_resp.raise_for_status()

                        text_parts = []
                        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
                            md_files = [n for n in zf.namelist() if n.endswith(".md")]
                            full_md = [n for n in md_files if n.endswith("full.md")]
                            target_files = full_md if full_md else sorted(md_files)

                            for md_name in target_files:
                                content = zf.read(md_name).decode("utf-8")
                                if content.strip():
                                    text_parts.append(content)

                        text = "\n\n".join(text_parts) if text_parts else ""

                        output_file = None
                        if output_dir and text:
                            out_dir = Path(output_dir)
                            out_dir.mkdir(parents=True, exist_ok=True)
                            stem = Path(file_name).stem
                            out_path = out_dir / f"{stem}.md"
                            out_path.write_text(text, encoding="utf-8")
                            output_file = str(out_path)

                        results.append({
                            "file": file_name,
                            "status": "success",
                            "text": text,
                            "output_file": output_file,
                        })

                    except Exception as e:
                        results.append({"file": file_name, "status": "error", "message": str(e)})

                break  # 当前批次处理完毕

        # 汇总
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = sum(1 for r in results if r.get("status") == "error")
        overall_status = "success" if error_count == 0 else ("partial" if success_count > 0 else "error")

        return {
            "status": overall_status,
            "engine": "MinerU API (vlm)",
            "summary": f"成功 {success_count} 个，失败 {error_count} 个，共 {len(file_paths)} 个文件",
            "results": results,
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "engine": "MinerU API", "message": "网络请求超时", "results": results}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "engine": "MinerU API", "message": "无法连接 MinerU 服务器", "results": results}
    except Exception as e:
        return {"status": "error", "engine": "MinerU API", "message": str(e), "results": results}
