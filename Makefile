# Makefile for Fuse AWS SAM Operations

.PHONY: build validate deploy delete test clean

build:
	sam build

validate:
	sam validate --lint

deploy:
	sam deploy --guided

delete:
	sam delete --stack-name fuse-sam

test:
	python -m unittest discover -s scripts -p "test_*.py"

clean:
	rmdir /s /q .aws-sam 2>nul || true
