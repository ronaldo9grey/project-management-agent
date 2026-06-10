#!/bin/bash

# 更新所有用户密码
# admin: Yjy@2026pr
# 其他: 姓名拼音首字母大写 + 手机后四位

PGPASSWORD="qv52A03xcxAQCoDglUJelm4Sb" psql -h localhost -U yjydb -d project_cost_tracking << 'EOF'

-- 更新admin密码
UPDATE personnel SET password = 'Yjy@2026pr' WHERE employee_id = '0001';

-- 更新其他人员密码 (姓名全拼首字母大写 + 手机后四位)
UPDATE personnel SET password = 'WuChengrong6300' WHERE employee_id = '13086746300';
UPDATE personnel SET password = 'ZhangGang3052' WHERE employee_id = '13132863052';
UPDATE personnel SET password = 'LuShuangli8012' WHERE employee_id = '13387768012';
UPDATE personnel SET password = 'TanWendong8824' WHERE employee_id = '13627768824';
UPDATE personnel SET password = 'YangHong3213' WHERE employee_id = '13708713213';
UPDATE personnel SET password = 'XiaoZixin6133' WHERE employee_id = '13768136133';
UPDATE personnel SET password = 'LanJunsheng9227' WHERE employee_id = '13977629227';
UPDATE personnel SET password = 'ZhangDi9627' WHERE employee_id = '13988039627';
UPDATE personnel SET password = 'LuHongdong5566' WHERE employee_id = '15007765566';
UPDATE personnel SET password = 'WangChao5938' WHERE employee_id = '15010285938';
UPDATE personnel SET password = 'LiaoYingxiang5210' WHERE employee_id = '15077685210';
UPDATE personnel SET password = 'LuoZhendong5830' WHERE employee_id = '15080655830';
UPDATE personnel SET password = 'CenXiya6065' WHERE employee_id = '15207866065';
UPDATE personnel SET password = 'TangChangting7256' WHERE employee_id = '15275517256';
UPDATE personnel SET password = 'HuangDongni9817' WHERE employee_id = '15777619817';
UPDATE personnel SET password = 'LiangYeling1077' WHERE employee_id = '15807761077';
UPDATE personnel SET password = 'HeBin5852' WHERE employee_id = '15877105852';
UPDATE personnel SET password = 'LuoLiqun6629' WHERE employee_id = '17878836629';
UPDATE personnel SET password = 'LuoXiaoxiang6559' WHERE employee_id = '18077686559';
UPDATE personnel SET password = 'FengEnlang1250' WHERE employee_id = '18172381250';
UPDATE personnel SET password = 'ZhengWangming1338' WHERE employee_id = '18175961338';
UPDATE personnel SET password = 'ChenZhenping9347' WHERE employee_id = '18177629347';
UPDATE personnel SET password = 'XueChuang1230' WHERE employee_id = '18207761230';
UPDATE personnel SET password = 'WangXuanyue2750' WHERE employee_id = '18278652750';
UPDATE personnel SET password = 'LuoLiying5623' WHERE employee_id = '18377615623';
UPDATE personnel SET password = 'SuJibo3318' WHERE employee_id = '18377683318';
UPDATE personnel SET password = 'HeXu1289' WHERE employee_id = '18778691289';
UPDATE personnel SET password = 'ZhouGuiping4197' WHERE employee_id = '18888464197';
UPDATE personnel SET password = 'LongHuaqiang1499' WHERE employee_id = '18907761499';
UPDATE personnel SET password = 'GuJinrong5721' WHERE employee_id = '19914945721';

-- 验证更新结果
SELECT employee_id, name, 
       CASE 
         WHEN employee_id = '0001' THEN 'Yjy@2026pr'
         ELSE '已更新'
       END as password_status
FROM personnel 
WHERE is_deleted = false 
ORDER BY employee_id;

EOF

echo ""
echo "===================="
echo "密码更新完成！"
echo "===================="
