.PHONY: build run

build:
	docker build -t heilsarmee-calendar .

run: build
	mkdir -p output
	docker run --rm -v "$(PWD)/output:/output" heilsarmee-calendar
	open output/
