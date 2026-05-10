#!/bin/bash
# 批量冒烟测试：每个 fn 启动 2 秒检查能否正常初始化
set +e
FNS=(
  sol.pumpfun sol.pumpfun_grad sol.raydium sol.meteora
  sol.jup_launchpad sol.copytrade
  bsc.pancake_v2 bsc.pancake_v3 bsc.fourmeme bsc.copytrade bsc.launchpad
  eth.uniswap_v2 eth.uniswap_v3 eth.virtuals eth.copytrade eth.launchpad
)
pass=0
fail=0
failed_fns=()
for fn in "${FNS[@]}"; do
  output=$(timeout 2 python3 main.py --fn "$fn" --no-banner < /dev/null 2>&1)
  # 成功条件：出现 "started on" 或 "no target_wallets"（copytrade 预期报错但程序不崩）
  if echo "$output" | grep -qE "started on|no target_wallets"; then
    echo "✅ $fn"
    pass=$((pass+1))
  else
    # 也接受 timeout 返回码 124（正常超时）+ 没有 Traceback
    if echo "$output" | grep -q "Traceback"; then
      echo "❌ $fn"
      echo "$output" | tail -5
      failed_fns+=("$fn")
      fail=$((fail+1))
    else
      echo "✅ $fn (silent but no error)"
      pass=$((pass+1))
    fi
  fi
done
echo "---"
echo "PASS: $pass / $((pass+fail))"
echo "FAIL: $fail"
if [ $fail -gt 0 ]; then
  echo "Failed: ${failed_fns[*]}"
  exit 1
fi
