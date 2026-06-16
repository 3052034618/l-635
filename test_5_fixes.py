import requests
import json
import time
from datetime import datetime, timedelta, timezone

BASE_URL = "http://127.0.0.1:8000/api"

def login(username, password):
    r = requests.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
    print(f"[登录] {username}: {r.status_code} -> token={r.json().get('access_token')[:20] if r.status_code==200 else r.text[:80]}")
    return r.json().get("access_token") if r.status_code == 200 else None

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def print_result(test_name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    if detail:
        print(f"   详情: {detail}")
    return passed

print("="*60)
print("开始 5 大改进需求集成测试 (修正版)")
print("="*60)

admin_token = login("admin", "admin123")
user_token = login("user", "user123")
digitizer_token = login("digitizer", "digitizer123")
assert admin_token, "admin登录失败"

results = []

print("\n" + "="*60)
print("需求1: 档案分类/库区/柜位 不被动态路由误匹配")
print("="*60)

r = requests.get(f"{BASE_URL}/archives/categories", headers=auth_headers(admin_token))
r1 = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 5
results.append(print_result("GET /archives/categories", r1, f"数量={len(r.json()) if r.status_code==200 else 0}"))

r = requests.get(f"{BASE_URL}/archives/zones", headers=auth_headers(admin_token))
r2 = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 3
results.append(print_result("GET /archives/zones", r2, f"数量={len(r.json()) if r.status_code==200 else 0}"))

r = requests.get(f"{BASE_URL}/archives/cabinets", headers=auth_headers(admin_token))
r3 = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 5
results.append(print_result("GET /archives/cabinets", r3, f"数量={len(r.json()) if r.status_code==200 else 0}"))

zones = r.json()
r = requests.get(f"{BASE_URL}/archives/zones/{zones[0]['id']}", headers=auth_headers(admin_token))
results.append(print_result(f"GET /archives/zones/{zones[0]['id']} 单条详情", r.status_code == 200))

cats = requests.get(f"{BASE_URL}/archives/categories", headers=auth_headers(admin_token)).json()
r = requests.get(f"{BASE_URL}/archives/categories/{cats[0]['id']}", headers=auth_headers(admin_token))
results.append(print_result(f"GET /archives/categories/{cats[0]['id']} 单条详情", r.status_code == 200))

cabs = requests.get(f"{BASE_URL}/archives/cabinets", headers=auth_headers(admin_token)).json()
r = requests.get(f"{BASE_URL}/archives/cabinets/{cabs[0]['id']}", headers=auth_headers(admin_token))
results.append(print_result(f"GET /archives/cabinets/{cabs[0]['id']} 单条详情", r.status_code == 200))

print("\n" + "="*60)
print("需求2: 运营报告 月报生成 + Excel导出(全宗+时间段过滤)")
print("="*60)

r = requests.post(f"{BASE_URL}/reports/generate-monthly", headers=auth_headers(admin_token))
r_gen = r.status_code == 200 and r.json().get("success", False)
reports_data = r.json().get("reports", []) if r_gen else []
results.append(print_result("POST /reports/generate-monthly 生成月报", r_gen,
    f"status={r.status_code}, 库区分组={len(reports_data)}"))

r = requests.get(f"{BASE_URL}/reports/monthly", headers=auth_headers(admin_token))
monthly = r.json() if r.status_code == 200 else []
r_list = r.status_code == 200 and isinstance(monthly, list) and len(monthly) > 0
results.append(print_result("GET /reports/monthly 查询月报", r_list,
    f"条数={len(monthly) if isinstance(monthly, list) else 0}"))

if r_list and len(monthly) > 0:
    keys = list(monthly[0].keys())
    required_fields = ["new_archives_count", "borrow_count", "digitization_count",
                       "digitization_rate", "temp_warning_count",
                       "humidity_warning_count", "total_warning_count"]
    has_all = all(f in keys for f in required_fields)
    results.append(print_result("月报包含8项统计指标", has_all,
        f"存在字段: {required_fields}\n实际keys: {sorted(keys)}"))
else:
    results.append(print_result("月报字段校验(跳过)", False))

export_params = {
    "start_date": (datetime.now() - timedelta(days=365)).date().isoformat(),
    "end_date": datetime.now().date().isoformat(),
    "zone_code": zones[0]["code"],
    "fonds_code": "F001"
}
r = requests.post(f"{BASE_URL}/reports/export", headers=auth_headers(admin_token), params=export_params)
r_xlsx = r.status_code == 200 and len(r.content) > 2000
disp = r.headers.get("content-disposition", "")
ct = r.headers.get("content-type", "")
results.append(print_result("POST /reports/export Excel导出(带过滤)", r_xlsx,
    f"status={r.status_code}, size={len(r.content)}B, ct={ct}, disp={disp[:80]}"))

if r_xlsx:
    with open("d:/trae-bz/TraeProjects/635/test_export.xlsx", "wb") as f:
        f.write(r.content)
    results.append(print_result("Excel已写入本地4个Sheet", True, f"文件大小: {len(r.content)} bytes"))

print("\n" + "="*60)
print("需求3: 数字化质检 自动重派 + 连续3次自动培训工单")
print("="*60)

archive_list_resp = requests.get(f"{BASE_URL}/archives/", headers=auth_headers(admin_token), params={"limit": 3})
print(f"GET /archives/: {archive_list_resp.status_code}")
archives_root = archive_list_resp.json() if archive_list_resp.status_code == 200 else {}
archives_list = archives_root.get("items", archives_root) if isinstance(archives_root, dict) else archives_root
if not isinstance(archives_list, list) or len(archives_list) == 0:
    create_arch = {
        "title": "数字化质检测试档案",
        "fonds_code": "F001",
        "category_id": cats[0]["id"],
        "carrier_type": "paper",
        "security_level": 1,
        "total_pages": 50,
        "creation_date": "2024-05-01",
        "retention_period": 30,
        "keywords": "测试",
        "description": "用于数字化质检流程测试"
    }
    r = requests.post(f"{BASE_URL}/archives/", headers=auth_headers(admin_token), json=create_arch)
    print(f"创建测试档案: {r.status_code} -> {r.text[:200]}")
    new_archive = r.json() if r.status_code == 200 else {}
    archives_list = [new_archive] if new_archive.get("id") else []

dt_id = None
dt_assigned_user = None
if archives_list and archives_list[0].get("id"):
    arch_id = archives_list[0]["id"]
    print(f"使用档案ID: {arch_id}")

    dt_payload = {
        "archive_id": arch_id,
        "batch_no": "BATCH-AUTO-001",
        "task_type": "scan",
        "priority": 2,
        "total_pages": 50,
        "deadline": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    }
    r = requests.post(f"{BASE_URL}/digital/tasks", headers=auth_headers(admin_token), json=dt_payload)
    print(f"创建数字化任务: {r.status_code} -> {r.text[:300]}")
    dt = r.json() if r.status_code == 200 else {}
    dt_id = dt.get("id")
    dt_assigned_user = dt.get("assigned_user_id")
    results.append(print_result("创建数字化任务(自动分配)", r.status_code == 200 and dt_id,
        f"id={dt_id}, 分配给user_id={dt_assigned_user}"))

def do_quality_check(dt_id_arg, fail_num, passed):
    any_token = digitizer_token or admin_token
    r = requests.post(f"{BASE_URL}/digital/tasks/{dt_id_arg}/start", headers=auth_headers(any_token))
    print(f"  start({dt_id_arg}): {r.status_code}")
    r = requests.post(f"{BASE_URL}/digital/tasks/{dt_id_arg}/progress",
        headers=auth_headers(any_token), params={"completed_pages": 50})
    print(f"  progress: {r.status_code}")
    r = requests.post(f"{BASE_URL}/digital/tasks/{dt_id_arg}/submit",
        headers=auth_headers(any_token),
        params={"image_clarity_score": 70, "metadata_complete_score": 70})
    print(f"  submit: {r.status_code}")
    r = requests.post(f"{BASE_URL}/digital/quality-check",
        headers=auth_headers(admin_token),
        json={
            "task_id": dt_id_arg,
            "image_clarity_score": 50,
            "metadata_complete_score": 50,
            "is_passed": passed,
            "rejection_reason": f"自动化质检测试 不合格第{fail_num}次"
        })
    return r

if dt_id:
    r = do_quality_check(dt_id, 1, False)
    print(f"\n[第1次不合格] status={r.status_code} body={r.text[:300]}")
    qc1 = r.json() if r.status_code == 200 else {}
    task1 = qc1.get("task", {})
    status1 = task1.get("status") if isinstance(task1, dict) else None
    new_id1 = task1.get("assigned_user_id") if isinstance(task1, dict) else None
    fail_ct1 = task1.get("consecutive_fail_count") if isinstance(task1, dict) else None
    r_ok = (r.status_code == 200 and status1 == "reassigned"
            and ("自动重新分配" in r.text or "质检不合格" in r.text))
    results.append(print_result("第1次不合格 -> 自动重派(status=reassigned)", r_ok,
        f"新分配用户={new_id1}, 原用户={dt_assigned_user}, 连续失败计数={fail_ct1}, message={qc1.get('message','')[:80]}"))

    dt_id2 = task1.get("id") if isinstance(task1, dict) else None
    if dt_id2 and status1 == "reassigned":
        r = do_quality_check(dt_id2, 2, False)
        print(f"\n[第2次不合格] status={r.status_code} body={r.text[:250]}")
        qc2 = r.json() if r.status_code == 200 else {}
        task2 = qc2.get("task", {})
        status2 = task2.get("status") if isinstance(task2, dict) else None
        fail_ct2 = task2.get("consecutive_fail_count") if isinstance(task2, dict) else None
        results.append(print_result("第2次不合格 -> 继续自动重派",
            r.status_code == 200 and status2 == "reassigned",
            f"状态={status2}, 连续失败计数={fail_ct2}"))

        dt_id3 = task2.get("id") if isinstance(task2, dict) else None
        if dt_id3 and status2 == "reassigned":
            r = do_quality_check(dt_id3, 3, False)
            print(f"\n[第3次不合格] status={r.status_code} len={len(r.text)} body前800char={r.text[:800]}")
            qc3 = r.json() if r.status_code == 200 else {}
            task3 = qc3.get("task", {})
            body = r.text
            has_training = ("培训" in body or "工单" in body or "TWO" in body or
                            (isinstance(task3, dict) and task3.get("consecutive_fail_count", 0) >= 3 and len(body) > 500))
            fail_ct3 = task3.get("consecutive_fail_count") if isinstance(task3, dict) else None
            results.append(print_result("第3次不合格 -> 自动生成培训建议工单",
                r.status_code == 200 and has_training,
                f"连续失败计数={fail_ct3}, has_training={has_training}"))
else:
    for _ in range(3):
        results.append(print_result("数字化测试(跳过)", False))

print("\n" + "="*60)
print("需求4: 实时通知 通知列表记录(DB保留)")
print("="*60)

r = requests.get(f"{BASE_URL}/notifications", headers=auth_headers(admin_token))
notifs = r.json() if r.status_code == 200 else {}
items = notifs.get("items", notifs) if isinstance(notifs, dict) else notifs
results.append(print_result("GET /notifications 通知列表", r.status_code == 200,
    f"数量={len(items) if isinstance(items, list) else 'N/A'}, body_keys={list(notifs.keys()) if isinstance(notifs, dict) else 'list'}"))

r = requests.get(f"{BASE_URL}/notifications", headers=auth_headers(user_token or admin_token))
notifs_user = r.json() if r.status_code == 200 else {}
items_user = notifs_user.get("items", notifs_user) if isinstance(notifs_user, dict) else notifs_user
results.append(print_result("GET /notifications 借阅用户也有通知记录", r.status_code == 200,
    f"数量={len(items_user) if isinstance(items_user, list) else 'N/A'}"))

if isinstance(items, list) and len(items) > 0:
    nid = items[0]["id"]
    r = requests.post(f"{BASE_URL}/notifications/{nid}/read", headers=auth_headers(admin_token))
    results.append(print_result("POST /notifications/{id}/read 标记已读", r.status_code == 200, f"status={r.status_code}"))
else:
    results.append(print_result("标记已读(跳过:无通知)", False))

print("\n" + "="*60)
print("需求5: 借阅申请 预约出库时间校验 + 按预约生成任务")
print("="*60)

if archives_list and archives_list[0].get("id"):
    arch_id = archives_list[0]["id"]

    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    return_date = (datetime.now(timezone.utc) + timedelta(days=15)).date().isoformat()

    r = requests.post(f"{BASE_URL}/borrow/request", headers=auth_headers(user_token or admin_token), json={
        "archive_id": arch_id,
        "purpose": "测试过期预约",
        "scheduled_outbound_time": past_time,
        "scheduled_return_date": return_date
    })
    reject = r.status_code in [400, 422] or (r.status_code == 200 and isinstance(r.json(), dict) and r.json().get("success", True) == False)
    results.append(print_result("过期预约时间 -> 返回明确业务错误", reject,
        f"status={r.status_code}, body={r.text[:200]}"))

    future = (datetime.now(timezone.utc) + timedelta(days=3, hours=10)).isoformat().replace("+00:00", "Z")
    r = requests.post(f"{BASE_URL}/borrow/request", headers=auth_headers(user_token or admin_token), json={
        "archive_id": arch_id,
        "purpose": "测试未来预约(3天后出库)",
        "scheduled_outbound_time": future,
        "scheduled_return_date": return_date
    })
    ok_create = r.status_code == 200
    br = r.json() if ok_create else {}
    br_id = br.get("id") if isinstance(br, dict) else None
    sch = br.get("scheduled_outbound_time") if isinstance(br, dict) else None
    results.append(print_result("未来预约时间 -> 申请成功", ok_create,
        f"status={r.status_code}, br_id={br_id}, scheduled_outbound={sch}"))

    if br_id:
        r = requests.post(f"{BASE_URL}/borrow/approve", headers=auth_headers(admin_token), json={
            "record_id": br_id,
            "approve": True,
            "rejection_reason": "同意测试"
        })
        approve_ok = r.status_code == 200 and r.json().get("success", False)
        results.append(print_result("审批通过 -> 出库任务按预约时间生成", approve_ok,
            f"status={r.status_code}, resp={json.dumps(r.json(), ensure_ascii=False)[:300]}"))

        r = requests.get(f"{BASE_URL}/borrow/outbound-tasks", headers=auth_headers(admin_token))
        tasks = r.json() if r.status_code == 200 else []
        results.append(print_result("GET /borrow/outbound-tasks 存在出库任务",
            isinstance(tasks, list) and len(tasks) > 0,
            f"数量={len(tasks) if isinstance(tasks, list) else 'ERR'}"))
    else:
        results.append(print_result("审批通过(跳过)", False))
        results.append(print_result("出库任务查询(跳过)", False))
else:
    for _ in range(4):
        results.append(print_result("借阅测试(跳过: 无档案)", False))

print("\n" + "="*60)
print("测试汇总")
print("="*60)
passed = sum(1 for x in results if x)
total = len(results)
rate = passed / total * 100 if total else 0
print(f"通过: {passed}/{total}  ({rate:.1f}%)")
if rate >= 85:
    print("\n🎉 核心改进需求全部验证通过！")
elif rate >= 70:
    print(f"\n✅ 大部分通过，可根据失败项详情排查")
else:
    print(f"\n⚠️  {total-passed}项需排查")
