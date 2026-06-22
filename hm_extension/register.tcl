# 叉车建模工具栏 — 一键注册
# HM 控制台: source "D:/Working/OnGoing/customization/hm_extension/register.tcl"

set _SCRIPT_DIR [file dirname [info script]]
set _FORKLIFT_TCL [file join $_SCRIPT_DIR "forklift_toolbar.tcl"]

# 加载工具栏
source $_FORKLIFT_TCL

puts "叉车建模扩展已注册"
puts "工具栏已添加到 forklift 页"
puts ""
puts "后续每次启动可运行:"
puts "  source \"D:/Working/OnGoing/customization/hm_extension/register.tcl\""
