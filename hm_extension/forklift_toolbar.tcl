# 叉车建模工具栏 — HyperWorks 2026
# 在 HM 命令窗口: source "D:/Working/OnGoing/customization/hm_extension/register.tcl"

set _PDIR "D:/Working/OnGoing/customization"

# Python 回调 — 通过 HM Python 桥执行
proc py_run {script} {
  global _PDIR
  # 先切目录，再 run 脚本
  set code "import os; os.chdir(r'${_PDIR}'); exec(open(r'${script}', encoding='utf-8').read())"
  *executepy ${code}
}

# 清除旧按钮
foreach btn {import midsurface mesh assign connector fullrun clear load} {
  catch "*destroybutton forklift ${btn}"
}

# 创建按钮
*createbutton forklift import    0 0 "[导入]"   "py_run tools/import_parasolid.py"    10
*createbutton forklift midsurface 0 1 "[中面]"  "py_run tools/extract_midsurface.py"  10
*createbutton forklift assign    0 2 "[赋参]"  "py_run tools/assign_property.py"     10
*createbutton forklift mesh      0 3 "[网格]"  "py_run tools/auto_mesh.py"           10
*createbutton forklift connector 0 4 "[连接]"  "py_run tools/create_connectors.py"   10
*createbutton forklift fullrun   0 5 "[全流程]" "py_run tools/run_all.py"             12
*createbutton forklift clear     1 0 "[清理]"  "py_run tools/clear_all.py"           8
*createbutton forklift load      1 1 "[函数]"  "py_run tools/load_all.py"            12

puts "叉车建模工具栏已加载 ( forklift page )"
