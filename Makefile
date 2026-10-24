PY ?= python3
REF = NANOSERVE_REFERENCE=1

.PHONY: progress reveal test test-ref test-fill m1 m2 m3 m4 m5 m6 m7 run demo demos callsites

progress:            ## 进度面板（无剧透）
	$(PY) tools/progress.py

reveal:              ## 进度面板 + 已完成练习对应的 LeetCode 题号
	$(PY) tools/progress.py --reveal

test:                ## 跑全部测试（你的实现）
	$(PY) -m pytest -q

test-ref:            ## 用参考解跑全部测试（需要 reference/）
	$(PY) -m pytest -q --reference

test-fill:           ## 集成测试：你写好的用你的，没写的用参考解顶上（需要 reference/）
	$(PY) -m pytest -q --fill tests/domain

m1 m2 m3 m4 m5 m6 m7:
	$(PY) tools/progress.py --ms $(shell echo $@ | tr a-z A-Z) --verbose

run:                 ## 用你自己的实现跑 M1
	$(PY) -m nanoserve "The scheduler" --max-tokens 60

demo:                ## 用参考解跑 M1（需要 reference/）
	$(REF) $(PY) -m nanoserve "The scheduler" --max-tokens 60

demos:               ## 用参考解把每个里程碑的 demo 都跑一遍（需要 reference/）
	@for c in generate serve kv prefix compile config eval bench dashboard autoscale; do \
	  echo "\n================ nanoserve $$c"; $(REF) $(PY) -m nanoserve $$c || exit 1; done

callsites:           ## 维护者自检：每个练习都被集成测试真实调用（需要 reference/ 和 coverage）
	$(PY) tools/callsites.py
