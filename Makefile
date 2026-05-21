.PHONY: build run

PDF = output/termine-heilsarmee-leipzig.pdf

build:
	docker build -t heilsarmee-calendar .

run: build
	mkdir -p output
	docker run --rm -v "$(PWD)/output:/output" heilsarmee-calendar
	open $(PDF)
