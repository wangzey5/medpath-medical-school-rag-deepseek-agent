import html
import json
import math
import os
import re
import ssl
import urllib.parse
import urllib.request
from datetime import date


OFFICIAL_SOURCES = [
    {
        "title": "AAMC - Applying to Medical School",
        "url": "https://students-residents.aamc.org/applying-medical-school/applying-medical-school",
        "topics": "AMCAS MD application timeline requirements medical school admissions",
    },
    {
        "title": "AAMC - AMCAS Application",
        "url": "https://students-residents.aamc.org/applying-medical-school-amcas/applying-medical-school-amcas",
        "topics": "AMCAS primary application transcript verification letters activities personal statement",
    },
    {
        "title": "AAMC - Medical School Admission Requirements (MSAR)",
        "url": "https://students-residents.aamc.org/medical-school-admission-requirements/medical-school-admission-requirements",
        "topics": "MSAR school comparison GPA MCAT prerequisites tuition deadlines",
    },
    {
        "title": "AAMC - MCAT",
        "url": "https://students-residents.aamc.org/taking-mcat-exam/taking-mcat-exam",
        "topics": "MCAT registration dates scores exam preparation",
    },
    {
        "title": "AACOM - Applying to Osteopathic Medical College",
        "url": "https://www.aacom.org/become-a-doctor/apply-to-medical-school",
        "topics": "AACOMAS DO osteopathic application timeline requirements",
    },
    {
        "title": "Choose DO Explorer",
        "url": "https://www.aacom.org/explore-med-schools/choose-do-explorer",
        "topics": "DO school comparison prerequisites tuition admissions",
    },
    {
        "title": "Federal Student Aid",
        "url": "https://studentaid.gov/",
        "topics": "FAFSA federal student aid loans medical school financial aid",
    },
]

GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7, "F": 0.0,
}

SUBJECT_ALIASES = {
    "biology": {"biology", "bio", "biological sciences", "生物", "生物学"},
    "general chemistry": {"general chemistry", "chemistry", "gen chem", "普通化学", "化学"},
    "organic chemistry": {"organic chemistry", "ochem", "有机化学"},
    "physics": {"physics", "物理", "物理学"},
    "biochemistry": {"biochemistry", "biochem", "生物化学"},
    "mathematics": {"mathematics", "math", "calculus", "statistics", "数学", "微积分", "统计"},
    "english": {"english", "writing", "composition", "英语", "写作"},
    "psychology": {"psychology", "psych", "心理学"},
    "sociology": {"sociology", "soc", "社会学"},
}


TOOL_LABELS = {
    "official_source_lookup": "官方来源检索",
    "build_application_timeline": "申请时间线",
    "compare_medical_schools": "院校比较",
    "evaluate_applicant_profile": "申请档案评估",
    "match_prerequisites": "先修课匹配",
    "application_calculator": "申请计算器",
}

TOOL_CONFIGS = {
    "official_source_lookup": {
        "label": "官方来源检索",
        "scope": "仅核验美国医学院申请政策、日期、要求、费用等官方信息，并返回官方来源链接。",
        "welcome": "告诉我需要核验的政策、日期、院校要求或官方信息。我只处理官方来源核验。",
        "keywords": ["官方", "来源", "核验", "政策", "截止", "日期", "官网", "aamc", "aacom", "amcas", "aacomas", "mcat", "学费"],
    },
    "build_application_timeline": {
        "label": "申请时间线",
        "scope": "仅生成和调整美国医学院申请时间线、里程碑及任务安排。",
        "welcome": "请提供目标入学年份、AMCAS/AACOMAS 申请体系、MCAT 日期和当前进度。",
        "keywords": ["时间线", "时间表", "规划", "入学年份", "申请年份", "mcat 日期", "里程碑", "何时", "什么时候", "安排"],
    },
    "compare_medical_schools": {
        "label": "院校比较",
        "scope": "仅依据用户或知识库提供的数据比较医学院，不预测录取概率。",
        "welcome": "请提供学校名单，以及希望比较的 GPA、MCAT、学费、州偏好或项目特点。",
        "keywords": ["院校", "学校", "比较", "选校", "md", "do", "gpa", "mcat", "学费", "州籍", "项目"],
    },
    "evaluate_applicant_profile": {
        "label": "申请档案评估",
        "scope": "仅检查医学院申请档案的完整度、缺失信息和明显短板，不预测录取概率。",
        "welcome": "请提供 GPA、MCAT、临床、跟诊、服务、科研和领导经历；也可以让我逐项询问。",
        "keywords": ["档案", "背景", "评估", "完整度", "短板", "经历", "临床", "跟诊", "志愿", "科研", "领导", "小时"],
    },
    "match_prerequisites": {
        "label": "先修课匹配",
        "scope": "仅将已修课程与目标医学院的先修课程要求进行匹配。",
        "welcome": "请提供已修课程，以及目标院校的官方 prerequisite 要求。",
        "keywords": ["先修", "课程", "学分", "实验课", "prerequisite", "biology", "chemistry", "physics", "生物", "化学", "物理"],
    },
    "application_calculator": {
        "label": "申请计算器",
        "scope": "仅计算 Overall/BCPM GPA 或美国医学院申请费用。",
        "welcome": "请选择计算 GPA 或申请费用，并提供课程成绩学分或费用明细。",
        "keywords": ["计算", "gpa", "bcpm", "成绩", "学分", "费用", "成本", "美元", "申请费", "总计"],
    },
}

OUT_OF_SCOPE_KEYWORDS = [
    "文书", "personal statement", "essay", "代写", "翻译", "天气", "新闻", "编程", "代码",
    "旅游", "菜谱", "股票", "投资", "诊断", "用药",
]


def tool_definition(name):
    return next((item for item in TOOL_DEFINITIONS if item["function"]["name"] == name), None)


def tool_question_in_scope(name, question, has_history=False):
    text = str(question or "").lower()
    if name not in TOOL_CONFIGS:
        return False
    if any(keyword in text for keyword in OUT_OF_SCOPE_KEYWORDS):
        return False
    scores = {
        tool_name: sum(1 for keyword in config["keywords"] if keyword in text)
        for tool_name, config in TOOL_CONFIGS.items()
    }
    current_score = scores[name]
    other_score = max((score for tool_name, score in scores.items() if tool_name != name), default=0)
    pattern_matches = {
        "build_application_timeline": bool(re.search(r"20\d{2}.{0,8}(?:入学|申请)|\d{4}-\d{2}-\d{2}", text)),
        "compare_medical_schools": bool(re.search(r"(?:university|college|school|大学|医学院)", text)),
        "evaluate_applicant_profile": bool(re.search(r"(?:gpa|mcat|\d+)\D{0,6}(?:小时|hours?)", text)),
        "match_prerequisites": bool(re.search(r"(?:bio|chem|physics|生物|化学|物理).{0,12}(?:学分|credits?|lab|实验)", text)),
        "application_calculator": bool(re.search(r"(?:[abcdf][+-]?\s*[,，/]?\s*\d+(?:\.\d+)?|\$\s*\d+)", text, re.I)),
        "official_source_lookup": bool(re.search(r"https?://", text)),
    }
    if pattern_matches.get(name):
        current_score += 5
    if current_score:
        return current_score >= other_score
    if has_history and other_score == 0:
        return True
    return False


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "official_source_lookup",
            "description": "查找或读取美国医学院申请相关的官方来源。用于政策、截止日期、MCAT、AMCAS、AACOMAS、学费和院校要求。只返回受允许的官方域名，并附 URL。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要核验的主题或问题"},
                    "official_url": {"type": "string", "description": "可选。用户或知识库已经提供的官方网页 URL"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_application_timeline",
            "description": "根据目标入学年份、申请体系和 MCAT 日期生成美国医学院申请规划时间线。日期是规划窗口，具体开放和截止日期仍需官方核验。",
            "parameters": {
                "type": "object",
                "properties": {
                    "matriculation_year": {"type": "integer", "description": "目标入学年份，例如 2027"},
                    "application_service": {"type": "string", "enum": ["AMCAS", "AACOMAS", "BOTH"]},
                    "mcat_date": {"type": "string", "description": "可选，YYYY-MM-DD"},
                    "current_stage": {"type": "string", "description": "可选，当前准备进度"},
                },
                "required": ["matriculation_year", "application_service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_medical_schools",
            "description": "比较用户提供或知识库提取的院校数据。不会自行编造学校指标；缺失字段会明确标记。",
            "parameters": {
                "type": "object",
                "properties": {
                    "schools": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "program_type": {"type": "string"},
                                "median_gpa": {"type": "number"},
                                "median_mcat": {"type": "number"},
                                "tuition": {"type": "number"},
                                "state_preference": {"type": "string"},
                                "notes": {"type": "string"},
                                "source": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "applicant_gpa": {"type": "number"},
                    "applicant_mcat": {"type": "number"},
                    "applicant_state": {"type": "string"},
                },
                "required": ["schools"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_applicant_profile",
            "description": "检查申请档案的完整度和明显短板，不预测录取概率。",
            "parameters": {
                "type": "object",
                "properties": {
                    "overall_gpa": {"type": "number"},
                    "science_gpa": {"type": "number"},
                    "mcat": {"type": "number"},
                    "clinical_hours": {"type": "number"},
                    "shadowing_hours": {"type": "number"},
                    "nonclinical_service_hours": {"type": "number"},
                    "research_hours": {"type": "number"},
                    "leadership": {"type": "boolean"},
                    "state_residency": {"type": "string"},
                    "target_program": {"type": "string", "enum": ["MD", "DO", "BOTH"]},
                },
                "required": ["target_program"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_prerequisites",
            "description": "将已修课程与院校先修课要求逐项匹配，输出满足、可能满足、缺失和需人工确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "courses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "subject": {"type": "string"},
                                "credits": {"type": "number"},
                                "has_lab": {"type": "boolean"},
                            },
                            "required": ["name", "credits"],
                        },
                    },
                    "requirements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subject": {"type": "string"},
                                "credits": {"type": "number"},
                                "lab_required": {"type": "boolean"},
                                "notes": {"type": "string"},
                            },
                            "required": ["subject", "credits"],
                        },
                    },
                },
                "required": ["courses", "requirements"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "application_calculator",
            "description": "精确计算 GPA 或申请成本。GPA 支持总 GPA 和 BCPM/science GPA；费用支持申请费、二次申请费、面试和其他成本。",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["gpa", "cost"]},
                    "courses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "grade": {"type": "string"},
                                "credits": {"type": "number"},
                                "category": {"type": "string", "description": "BCPM/science 或 other"},
                            },
                            "required": ["name", "grade", "credits"],
                        },
                    },
                    "cost_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "unit_cost": {"type": "number"},
                                "quantity": {"type": "number"},
                            },
                            "required": ["name", "unit_cost", "quantity"],
                        },
                    },
                },
                "required": ["operation"],
            },
        },
    },
]


def _normalize_subject(value):
    value = re.sub(r"\s+", " ", str(value or "").strip().lower())
    for canonical, aliases in SUBJECT_ALIASES.items():
        if value in aliases or any(alias in value for alias in aliases):
            return canonical
    return value


def _allowed_official_url(url):
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    return (
        host == "aamc.org" or host.endswith(".aamc.org")
        or host == "aacom.org" or host.endswith(".aacom.org")
        or host == "choose.do" or host.endswith(".choose.do")
        or host == "studentaid.gov" or host.endswith(".studentaid.gov")
        or host.endswith(".edu")
    )


def official_source_lookup(query, official_url=""):
    expanded_query = query.lower()
    translations = {
        "时间": " timeline dates", "截止": " deadline", "申请": " application",
        "医学院": " medical school", "学费": " tuition", "先修": " prerequisites",
        "助学": " financial aid", "贷款": " loans", "考试": " exam",
    }
    for chinese, english in translations.items():
        if chinese in query:
            expanded_query += english
    query_tokens = set(re.findall(r"[a-z0-9]+", expanded_query))
    ranked = []
    for source in OFFICIAL_SOURCES:
        haystack = f"{source['title']} {source['topics']}".lower()
        score = sum(1 for token in query_tokens if token in haystack)
        ranked.append((score, source))
    ranked.sort(key=lambda item: item[0], reverse=True)
    result = {
        "query": query,
        "sources": [item[1] for item in ranked[:4]],
        "notice": "这些是官方入口。具体日期、学费和院校要求需在对应页面核验发布日期与申请周期。",
    }
    if official_url:
        if not _allowed_official_url(official_url):
            result["page_error"] = "拒绝读取非官方域名；仅允许 AAMC、AACOM、Choose DO、StudentAid 和 .edu。"
        else:
            try:
                request = urllib.request.Request(official_url, headers={"User-Agent": "MedPath/1.0"})
                with urllib.request.urlopen(request, timeout=15, context=_tls_context()) as response:
                    content_type = response.headers.get("Content-Type", "")
                    raw = response.read(300000).decode("utf-8", errors="replace")
                if "html" in content_type or "<html" in raw.lower():
                    raw = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", raw, flags=re.I)
                    raw = re.sub(r"<[^>]+>", " ", raw)
                    raw = html.unescape(raw)
                text = re.sub(r"\s+", " ", raw).strip()
                result["page"] = {"url": official_url, "excerpt": text[:6000]}
            except Exception as exc:
                result["page_error"] = f"官方页面读取失败：{exc}"
    return result


def _tls_context():
    custom_ca = os.environ.get("DEEPSEEK_CA_BUNDLE", "").strip()
    if custom_ca:
        return ssl.create_default_context(cafile=custom_ca)
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def build_application_timeline(matriculation_year, application_service, mcat_date="", current_stage=""):
    cycle_year = int(matriculation_year) - 1
    service = application_service.upper()
    milestones = [
        {"window": f"{cycle_year - 1}-09 至 {cycle_year}-01", "task": "确认申请目标、先修课缺口、推荐信人选和 MCAT 计划"},
        {"window": f"{cycle_year}-01 至 {cycle_year}-03", "task": "准备个人陈述、活动经历清单，索取非官方成绩单核对课程"},
        {"window": f"{cycle_year}-03 至 {cycle_year}-04", "task": "确定初步选校范围，提醒推荐人并准备成绩单发送流程"},
        {"window": f"{cycle_year}-05", "task": f"关注 {service} 当季申请开放日期并开始录入材料"},
        {"window": f"{cycle_year}-05 至 {cycle_year}-06", "task": "完成最终校对；开放提交后尽早提交，不把规划日期当作官方截止日期"},
        {"window": f"{cycle_year}-06 至 {cycle_year}-09", "task": "跟踪验证状态并在收到 secondary 后按计划完成"},
        {"window": f"{cycle_year}-08 至 {matriculation_year}-03", "task": "准备面试、更新信及录取后事项"},
        {"window": f"{matriculation_year}-02 至 {matriculation_year}-07", "task": "比较录取、完成财务援助、背景调查和入学要求"},
    ]
    warnings = []
    if mcat_date:
        try:
            exam_date = date.fromisoformat(mcat_date)
            if exam_date.year > cycle_year or (exam_date.year == cycle_year and exam_date.month > 7):
                warnings.append("MCAT 日期较晚，可能影响选校和材料完整时间；请核对成绩发布日期。")
            milestones.insert(3, {"window": mcat_date, "task": "参加 MCAT；成绩发布日期以 AAMC 官方安排为准"})
        except ValueError:
            warnings.append("MCAT 日期格式无效，应为 YYYY-MM-DD。")
    return {
        "matriculation_year": matriculation_year,
        "application_service": service,
        "current_stage": current_stage,
        "milestones": milestones,
        "warnings": warnings,
        "official_sources": [OFFICIAL_SOURCES[0], OFFICIAL_SOURCES[1], OFFICIAL_SOURCES[4]],
        "notice": "此工具生成规划窗口，不代表当季官方开放日或学校截止日。",
    }


def compare_medical_schools(schools, applicant_gpa=None, applicant_mcat=None, applicant_state=""):
    rows = []
    for school in schools[:20]:
        missing = [
            field for field in ("program_type", "median_gpa", "median_mcat", "tuition", "state_preference", "source")
            if school.get(field) in (None, "")
        ]
        fit_signals = []
        if applicant_gpa is not None and school.get("median_gpa") is not None:
            delta = round(float(applicant_gpa) - float(school["median_gpa"]), 2)
            fit_signals.append(f"GPA 与所给中位数差值 {delta:+.2f}")
        if applicant_mcat is not None and school.get("median_mcat") is not None:
            delta = int(applicant_mcat) - int(school["median_mcat"])
            fit_signals.append(f"MCAT 与所给中位数差值 {delta:+d}")
        if applicant_state and school.get("state_preference"):
            fit_signals.append(f"州偏好需结合申请人州籍 {applicant_state} 核对")
        rows.append({
            "name": school.get("name", "未命名院校"),
            "provided_data": school,
            "fit_signals": fit_signals,
            "missing_fields": missing,
        })
    return {
        "schools": rows,
        "notice": "差值仅用于整理选校信息，不等于录取概率或 Reach/Target/Safety 结论。缺失数据必须从 MSAR、Choose DO 或院校官网补齐。",
    }


def evaluate_applicant_profile(target_program, **profile):
    fields = {
        "overall_gpa": "总 GPA", "science_gpa": "Science/BCPM GPA", "mcat": "MCAT",
        "clinical_hours": "临床经历", "shadowing_hours": "跟诊经历",
        "nonclinical_service_hours": "非临床服务", "research_hours": "科研经历",
        "leadership": "领导经历", "state_residency": "州籍",
    }
    missing = [label for key, label in fields.items() if profile.get(key) in (None, "")]
    flags = []
    if profile.get("clinical_hours") is not None and float(profile["clinical_hours"]) == 0:
        flags.append("未记录临床经历，无法体现对医疗环境的实际接触。")
    if profile.get("shadowing_hours") is not None and float(profile["shadowing_hours"]) == 0:
        flags.append("未记录 physician shadowing；应结合目标院校要求和个人经历判断。")
    if profile.get("nonclinical_service_hours") is not None and float(profile["nonclinical_service_hours"]) == 0:
        flags.append("未记录非临床社区服务。")
    if target_program in {"DO", "BOTH"}:
        flags.append("申请 DO 项目时，应确认是否理解 osteopathic medicine，并核对院校对 DO physician exposure 的偏好。")
    completed = len(fields) - len(missing)
    return {
        "target_program": target_program,
        "profile": profile,
        "completeness": {"completed": completed, "total": len(fields), "percent": round(completed / len(fields) * 100)},
        "missing": missing,
        "review_flags": flags,
        "notice": "这是资料完整性检查，不是录取概率评估。经历质量、持续性、反思和学校使命匹配不能只用小时数衡量。",
    }


def match_prerequisites(courses, requirements):
    normalized_courses = []
    for course in courses:
        subject = _normalize_subject(course.get("subject") or course.get("name"))
        normalized_courses.append({**course, "normalized_subject": subject})
    results = []
    for requirement in requirements:
        subject = _normalize_subject(requirement.get("subject"))
        matches = [course for course in normalized_courses if course["normalized_subject"] == subject]
        credits = sum(float(course.get("credits", 0)) for course in matches)
        lab_required = bool(requirement.get("lab_required"))
        has_lab = any(bool(course.get("has_lab")) for course in matches)
        if credits >= float(requirement.get("credits", 0)) and (not lab_required or has_lab):
            status = "satisfied"
        elif matches and credits > 0:
            status = "possibly_satisfied" if credits >= float(requirement.get("credits", 0)) else "missing"
        else:
            status = "missing"
        notes = []
        if lab_required and not has_lab:
            notes.append("未确认实验课")
        if matches and any(not course.get("subject") for course in matches):
            notes.append("依据课程名称推断学科，需人工核对")
        results.append({
            "requirement": requirement,
            "status": status,
            "matched_courses": matches,
            "matched_credits": credits,
            "notes": notes,
        })
    return {
        "results": results,
        "notice": "课程名称匹配不能替代院校审核。AP、在线课程、国际课程和跨学科课程尤其需要向学校确认。",
    }


def application_calculator(operation, courses=None, cost_items=None):
    if operation == "gpa":
        rows = []
        total_points = total_credits = science_points = science_credits = 0.0
        ignored = []
        for course in courses or []:
            grade = str(course.get("grade", "")).strip().upper()
            if grade not in GRADE_POINTS:
                ignored.append({"name": course.get("name"), "reason": f"不支持的成绩 {grade}"})
                continue
            credits = float(course.get("credits", 0))
            points = GRADE_POINTS[grade] * credits
            science = str(course.get("category", "")).lower() in {"bcpm", "science", "科学", "理科"}
            total_points += points
            total_credits += credits
            if science:
                science_points += points
                science_credits += credits
            rows.append({**course, "grade_points": GRADE_POINTS[grade], "quality_points": round(points, 3), "science": science})
        return {
            "operation": "gpa",
            "overall_gpa": round(total_points / total_credits, 3) if total_credits else None,
            "science_gpa": round(science_points / science_credits, 3) if science_credits else None,
            "total_credits": total_credits,
            "science_credits": science_credits,
            "courses": rows,
            "ignored": ignored,
            "notice": "这是规划估算。AMCAS/AACOMAS 的课程分类、重复课程和特殊成绩处理应以当季官方指南为准。",
        }
    if operation == "cost":
        rows = []
        total = 0.0
        for item in cost_items or []:
            subtotal = float(item.get("unit_cost", 0)) * float(item.get("quantity", 0))
            rows.append({**item, "subtotal": round(subtotal, 2)})
            total += subtotal
        return {"operation": "cost", "items": rows, "total": round(total, 2), "currency": "USD"}
    raise ValueError("不支持的计算类型")


def execute_tool(name, arguments):
    functions = {
        "official_source_lookup": official_source_lookup,
        "build_application_timeline": build_application_timeline,
        "compare_medical_schools": compare_medical_schools,
        "evaluate_applicant_profile": evaluate_applicant_profile,
        "match_prerequisites": match_prerequisites,
        "application_calculator": application_calculator,
    }
    if name not in functions:
        raise ValueError(f"未知工具：{name}")
    return functions[name](**arguments)


def tool_result_json(result):
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
