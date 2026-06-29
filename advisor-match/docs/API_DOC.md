# 导师智能推荐系统 API 文档

## 健康检查

`GET /api/health`

返回当前服务状态、表名、字段和最新清洗数据记录数，不返回本地绝对路径。

## 导师匹配

`POST /api/match`

### 请求字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `province` | string | 是 | 地区，只允许 `南京` 或 `云南` |
| `title` | string | 是 | 导师职称；`不限` 或空字符串表示不限制 |
| `expected_direction` | string | 是 | 学生期望研究方向，用于 TF-IDF 相似度匹配；不能为空 |

### 请求示例

```json
{
  "province": "云南",
  "title": "教授",
  "expected_direction": "无机化学、稀贵金属分离、物理化学"
}
```

### 成功响应

```json
{
  "success": true,
  "message": "匹配成功",
  "recommendations": [
    {
      "id": "1",
      "name": "张三",
      "title": "教授",
      "school": "某某大学",
      "province": "云南",
      "college": "某某学院",
      "area": "自然语言处理、知识图谱",
      "score": 0.9132,
      "email": "",
      "homepage_url": "",
      "match_reason": "暂无智能推荐理由"
    }
  ],
  "total": 1
}
```

没有符合条件的导师时，`recommendations` 返回空数组，HTTP 状态仍为 200。

## AI 接口

`GET /api/ai/test`

测试豆包 Ark Responses API 是否可用，成功返回“豆包 API 已成功接入”。

`POST /api/ai/compare`

请求体：

```json
{
  "mentors": []
}
```

也兼容字段名 `advisors`。需要选择 2 到 3 位导师。

`POST /api/ai/favorites`

请求体：

```json
{
  "mentors": []
}
```

也兼容字段名 `advisors`。心仪导师列表不能为空。

## 字段说明

当前正式返回字段为：

`id/name/title/school/province/college/area/score/email/homepage_url/match_reason`

已取消旧字段：学校等级、专业、科研产出。不再作为请求字段、数据字段或返回字段。
