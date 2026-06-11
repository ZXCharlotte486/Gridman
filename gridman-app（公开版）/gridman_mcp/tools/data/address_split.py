"""地址拆分工具

功能：
将完整地址拆分为省、市、区三级信息，用于函证发送。
可选按行政区划匹配邮政编码（数据源：tombcato/china-zipcode-data，MIT，2023版行政区划）。
"""
import re
import json
import pandas as pd
from pathlib import Path

from gridman_mcp.tools._shared.io import read_table


# 邮编数据文件（与本模块同目录）
_ZIPCODE_FILE = Path(__file__).parent / "china_zipcode_adcode.json"
# 邮编索引缓存（首次使用时加载）
_ZIPCODE_INDEX = None


def _load_zipcode_index() -> dict:
    """加载邮编数据并构建查询索引（懒加载 + 进程内缓存）。

    返回的索引含三级 key，匹配时由细到粗回退：
      - "省|市|区" → zipCode（最精确）
      - "省|市"     → 该市下任一区县的 zipCode（市级近似）
    数据缺失或解析失败时返回空 dict，邮编列留空，不影响地址拆分主流程。
    """
    global _ZIPCODE_INDEX
    if _ZIPCODE_INDEX is not None:
        return _ZIPCODE_INDEX

    index = {"district": {}, "city": {}, "prov_district": {}}
    try:
        with open(_ZIPCODE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            prov = item.get("province", "")
            city = item.get("city", "")
            name = item.get("name", "")
            zipcode = item.get("zipCode", "")
            if not zipcode:
                continue
            # 区县级精确索引
            if prov and city and name:
                index["district"][f"{prov}|{city}|{name}"] = zipcode
            # 省+区县索引（兜底直辖市等 city 字段写法不一致的情况，如重庆 city="重庆城区"）
            if prov and name:
                index["prov_district"].setdefault(f"{prov}|{name}", zipcode)
            # 市级近似索引（取该市第一个出现的区县邮编作为兜底）
            if prov and city:
                index["city"].setdefault(f"{prov}|{city}", zipcode)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        pass

    _ZIPCODE_INDEX = index
    return index


def _match_zipcode(province: str, city: str, district: str, index: dict) -> str:
    """按 省/市/区 匹配邮编，由细到粗回退。匹配不到返回空串。"""
    if not index or not index.get("district"):
        return ""
    # 1. 区县级精确匹配（省+市+区）
    if province and city and district:
        zc = index["district"].get(f"{province}|{city}|{district}")
        if zc:
            return zc
    # 2. 省+区县匹配（兜底直辖市等 city 字段写法不一致：如重庆 city="重庆城区"）
    if province and district:
        zc = index.get("prov_district", {}).get(f"{province}|{district}")
        if zc:
            return zc
    # 3. 市级近似匹配（区县匹配不到时退到市级）
    if province and city:
        zc = index["city"].get(f"{province}|{city}")
        if zc:
            return zc
    return ""


# 直辖市
MUNICIPALITIES = ["北京", "天津", "上海", "重庆"]

# 自治区简称映射
AUTONOMOUS_REGIONS = {
    "内蒙古": "内蒙古自治区",
    "广西": "广西壮族自治区",
    "西藏": "西藏自治区",
    "宁夏": "宁夏回族自治区",
    "新疆": "新疆维吾尔自治区",
}

# 省份列表（用于匹配）
PROVINCES = [
    "北京市", "天津市", "上海市", "重庆市",
    "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省",
    "山东省", "河南省", "湖北省", "湖南省", "广东省",
    "海南省", "四川省", "贵州省", "云南省", "陕西省",
    "甘肃省", "青海省", "台湾省",
    "内蒙古自治区", "广西壮族自治区", "西藏自治区",
    "宁夏回族自治区", "新疆维吾尔自治区",
    "香港特别行政区", "澳门特别行政区",
]

# 省份简称
PROVINCE_SHORT = {
    "北京": "北京市", "天津": "天津市", "上海": "上海市", "重庆": "重庆市",
    "河北": "河北省", "山西": "山西省", "辽宁": "辽宁省", "吉林": "吉林省",
    "黑龙江": "黑龙江省", "江苏": "江苏省", "浙江": "浙江省", "安徽": "安徽省",
    "福建": "福建省", "江西": "江西省", "山东": "山东省", "河南": "河南省",
    "湖北": "湖北省", "湖南": "湖南省", "广东": "广东省", "海南": "海南省",
    "四川": "四川省", "贵州": "贵州省", "云南": "云南省", "陕西": "陕西省",
    "甘肃": "甘肃省", "青海": "青海省", "台湾": "台湾省",
    "内蒙古": "内蒙古自治区", "广西": "广西壮族自治区",
    "西藏": "西藏自治区", "宁夏": "宁夏回族自治区", "新疆": "新疆维吾尔自治区",
    "香港": "香港特别行政区", "澳门": "澳门特别行政区",
}


def split_address(
    file_path: str,
    address_column: str = "地址",
    output_path: str = None,
    add_zipcode: bool = True,
) -> dict:
    """地址拆分为省市区，可选匹配邮政编码。

    Args:
        file_path: 包含地址列的 Excel/CSV 文件路径
        address_column: 地址列名
        output_path: 输出文件路径
        add_zipcode: 是否按行政区划匹配邮编列（默认 True）

    Returns:
        处理结果
    """
    try:
        try:
            df = read_table(file_path)
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        if address_column not in df.columns:
            return {"status": "error", "message": f"找不到列 '{address_column}'，可用列: {list(df.columns)}"}

        zip_index = _load_zipcode_index() if add_zipcode else None

        # 拆分每个地址
        results = []
        zip_matched = 0
        for addr in df[address_column]:
            parsed = _parse_address(str(addr) if pd.notna(addr) else "")
            if add_zipcode:
                zipcode = _match_zipcode(parsed["省"], parsed["市"], parsed["区"], zip_index)
                parsed["邮编"] = zipcode
                if zipcode:
                    zip_matched += 1
            results.append(parsed)

        result_df = pd.DataFrame(results)
        # 列名冲突保护：原表若已有"省/市/区/详细地址/邮编"等同名列，
        # 先删掉旧列再拼接，避免出现"邮编.1"这种重复列。
        dup_cols = [c for c in result_df.columns if c in df.columns]
        if dup_cols:
            df = df.drop(columns=dup_cols)
        output_df = pd.concat([df, result_df], axis=1)

        # 输出
        fp = Path(file_path)
        if output_path is None:
            output_path = fp.parent / "地址拆分结果.xlsx"
        else:
            output_path = Path(output_path)

        try:
            output_df.to_excel(output_path, index=False)
        except PermissionError:
            return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{output_path}"}

        # 解析成功的判定：省或市至少有一个（容忍只到市级的地址）
        success_count = sum(1 for r in results if r["省"] or r["市"])

        result = {
            "status": "success",
            "message": "地址拆分完成",
            "total_rows": int(len(df)),
            "parsed_success": int(success_count),
            "parsed_fail": int(len(df) - success_count),
            "output_file": str(output_path),
        }
        if add_zipcode:
            result["zipcode_matched"] = int(zip_matched)
            result["zipcode_unmatched"] = int(len(df) - zip_matched)
            if not zip_index or not zip_index.get("district"):
                result["zipcode_note"] = "邮编数据未加载（china_zipcode_adcode.json 缺失或损坏），邮编列为空"
        return result

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}


# 主要城市→省映射（用于地址不含省字头时反推）
CITY_TO_PROVINCE = {
    "广州市": "广东省", "深圳市": "广东省", "东莞市": "广东省", "佛山市": "广东省",
    "珠海市": "广东省", "中山市": "广东省", "惠州市": "广东省",
    "杭州市": "浙江省", "宁波市": "浙江省", "温州市": "浙江省", "嘉兴市": "浙江省",
    "南京市": "江苏省", "苏州市": "江苏省", "无锡市": "江苏省", "常州市": "江苏省",
    "济南市": "山东省", "青岛市": "山东省", "烟台市": "山东省",
    "武汉市": "湖北省", "长沙市": "湖南省", "合肥市": "安徽省", "南昌市": "江西省",
    "福州市": "福建省", "厦门市": "福建省", "泉州市": "福建省",
    "成都市": "四川省", "重庆市": "重庆市", "贵阳市": "贵州省", "昆明市": "云南省",
    "西安市": "陕西省", "兰州市": "甘肃省", "西宁市": "青海省",
    "石家庄市": "河北省", "太原市": "山西省", "郑州市": "河南省",
    "沈阳市": "辽宁省", "大连市": "辽宁省", "长春市": "吉林省", "哈尔滨市": "黑龙江省",
    "南宁市": "广西壮族自治区", "海口市": "海南省",
    "呼和浩特市": "内蒙古自治区", "银川市": "宁夏回族自治区",
    "拉萨市": "西藏自治区", "乌鲁木齐市": "新疆维吾尔自治区",
}


def _parse_address(address: str) -> dict:
    """解析单个地址为省市区"""
    result = {"省": "", "市": "", "区": "", "详细地址": address}

    if not address:
        return result

    remaining = address

    # 1. 提取省份
    province = ""
    for full_name in PROVINCES:
        if remaining.startswith(full_name):
            province = full_name
            remaining = remaining[len(full_name):]
            break

    if not province:
        for short, full in PROVINCE_SHORT.items():
            if remaining.startswith(short):
                province = full
                remaining = remaining[len(short):]
                # 去掉可能的"省"、"市"后缀
                if remaining and remaining[0] in "省市":
                    remaining = remaining[1:]
                break

    result["省"] = province

    # 2. 提取市
    # 顺序很重要：
    #   ① 先匹配"自治州/盟"——这俩是无歧义的地级后缀，且常跟县级市（如
    #      "恩施土家族苗族自治州利川市"），必须在此截断，否则 (.+?市) 会一路
    #      吃到县级"利川市"，把州和下属市揉成一团。
    #   ② 再匹配"市"——正常地级市。
    #   ③ 最后才用"地区/州"兜底——"地区"是常用词（"某地区办公室"），只在
    #      前面都没匹配到时才用，避免误把详细地址里的"地区"当成市。
    city_match = re.match(r"(.+?(?:自治州|盟))", remaining)
    if not city_match:
        city_match = re.match(r"(.+?市)", remaining)
    if not city_match:
        city_match = re.match(r"(.+?(?:地区|州))", remaining)
    if city_match:
        result["市"] = city_match.group(1)
        remaining = remaining[len(city_match.group(1)):]
    elif province in ["北京市", "天津市", "上海市", "重庆市"]:
        # 直辖市，市就是省
        result["市"] = province

    # 2.5. 反推：如果省为空但市能匹配主要城市，回填省
    if not result["省"] and result["市"] in CITY_TO_PROVINCE:
        result["省"] = CITY_TO_PROVINCE[result["市"]]

    # 3. 提取区
    district_match = re.match(r"(.+?(?:区|县|市|旗))", remaining)
    if district_match:
        result["区"] = district_match.group(1)
        remaining = remaining[len(district_match.group(1)):]

    result["详细地址"] = remaining if remaining else address

    return result
