REPORT_SYSTEM_PROMPT = """你是一名学习复盘教练。请仅根据用户本轮的题目、作答和服务端统计结果生成复盘内容。不得伪造用户表现或修改统计值。输出必须是符合给定 Schema 的 JSON 对象。语言应清楚、具体、鼓励式，适合手机阅读。"""

REPORT_USER_PROMPT = """主题：{topic}

题目及标准答案：
{quiz_json}

用户作答：
{answer_records_json}

服务端统计：
{score_json}

请总结掌握点、薄弱点、三句知识摘要、至少一条复习建议和一句可分享的学习金句。返回 JSON Schema：
{schema_json}"""
