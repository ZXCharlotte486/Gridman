"""
审计标识体系（参考天职国际《实质性程序审计工作底稿编制指引》2008）

用于古立特生成的审计明细表自动添加标准审计标识，让底稿"看起来像专业底稿"。

行业通用标识（2026 年仍在使用）：
- B    期初余额与上年审定数核对一致
- G    与总账核对相符
- S    与明细分类账核对相符
- T/B  与试算平衡表核对相符
- F/S  与已审计会计报表核对相符
- T    与原始凭证核对相符
- R    与文件依据核对相符
- C    已发询证函
- ?    已收回询证函
- AJE  调整分录
- RJE  重分类分录
- N/A  无此情况，不适用
- O→   交叉索引号

调整分录类型：
- S    Standard Adjustment（标准调整）
- AJE  Adjusting Journal Entry（调整分录）
- RJE  Reclassification Journal Entry（重分类分录）

使用示例：
    from gridman_mcp.tools._shared._audit_marks import AUDIT_MARKS, format_marks

    # 在合计行加 T/B 和 G 标识
    cell.value = format_marks(123456.78, ['T/B', 'G'])
    # → "123,456.78 (T/B G)"

    # 或者直接用常量
    AUDIT_MARKS['期初余额']  # → 'B'
"""

# 标准审计标识表
AUDIT_MARKS = {
    # 数据来源核对
    "期初余额": "B",
    "上年发生额": "B",
    "总账": "G",
    "明细账": "S",
    "试算平衡": "T/B",
    "已审报表": "F/S",
    "原始凭证": "T",
    "文件依据": "R",

    # 函证状态
    "已发函": "C",
    "已回函": "?",

    # 调整分录类型
    "调整分录": "AJE",
    "重分类": "RJE",
    "标准调整": "S",

    # 计算复核
    "纵向复核": ">",
    "横向复核": "<",
    "乘除核对": "X",

    # 状态
    "无此情况": "N/A",
    "重点关注": "△",
    "数据待查": "?",
    "数据有误": "×",
    "疑点已清": "✓",
    "数据待详查": "—",

    # 其他
    "结论": "CON",
    "注释": "NOTE",
    "交叉索引": "O→",
    "期后收付测试": "S/S",
}


def format_marks(value, marks=None, separator=" "):
    """
    给值附加审计标识。

    Args:
        value: 数值或字符串
        marks: 标识列表，如 ['T/B', 'G'] 或 ['B']
        separator: 标识之间的分隔符

    Returns:
        str: "数值 (标识1 标识2)"
    """
    if marks is None or len(marks) == 0:
        return value
    if isinstance(value, (int, float)):
        return f"{value:,.2f} ({separator.join(marks)})"
    return f"{value} ({separator.join(marks)})"


def get_mark_legend():
    """返回标识图例文本（供放在底稿尾部）"""
    return """审计标识说明:
B   期初余额与上年审定数核对一致
G   与总账核对相符
S   与明细分类账核对相符
T/B 与试算平衡表核对相符
F/S 与已审计会计报表核对相符
T   与原始凭证核对相符
R   与文件依据核对相符
C   已发询证函   ?   已收回询证函
AJE 调整分录    RJE 重分类分录
N/A 无此情况，不适用
"""


def get_mark_legend_table_rows():
    """返回标识图例的表格数据（[标识, 含义] 的列表）"""
    return [
        ("B", "期初余额与上年审定数核对一致"),
        ("G", "与总账核对相符"),
        ("S", "与明细分类账核对相符"),
        ("T/B", "与试算平衡表核对相符"),
        ("F/S", "与已审计会计报表核对相符"),
        ("T", "与原始凭证核对相符"),
        ("R", "与文件依据核对相符"),
        ("C", "已发询证函"),
        ("?", "已收回询证函"),
        ("AJE", "调整分录"),
        ("RJE", "重分类分录"),
        ("S", "标准调整"),
        ("N/A", "无此情况，不适用"),
        ("O→", "交叉索引号"),
    ]
