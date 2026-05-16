PODMAN ?= podman
IMAGE_REPO ?= localhost/quant-prototype
IMAGE ?= $(IMAGE_REPO):latest
TEST_IMAGE ?= $(IMAGE_REPO):test
CONTAINERFILE ?= Containerfile
IMAGE_LABEL ?= quant.project=quant-prototype

.PHONY: help clean-old-images build build-test test pipeline shell

help:
	@echo "Targets:"
	@echo "  make build      - Build runtime image"
	@echo "  make test       - Build test image and run pytest in container"
	@echo "  make pipeline   - Run full quant pipeline in container"
	@echo "  make shell      - Open interactive shell in runtime container"
	@echo "  make clean-old-images - Remove older quant-prototype images"

clean-old-images:
	@ids="$$( { \
		$(PODMAN) images "$(IMAGE_REPO)" -q 2>/dev/null || true; \
		$(PODMAN) images --filter label=$(IMAGE_LABEL) -q 2>/dev/null || true; \
	} | sort -u )"; \
	if [ -n "$$ids" ]; then \
		echo "Removing old quant-prototype images..."; \
		$(PODMAN) image rm -f $$ids >/dev/null || true; \
	else \
		echo "No old quant-prototype images found."; \
	fi

build: clean-old-images
	$(PODMAN) build -f $(CONTAINERFILE) --target base --label $(IMAGE_LABEL) -t $(IMAGE) .

build-test: clean-old-images
	$(PODMAN) build -f $(CONTAINERFILE) --label $(IMAGE_LABEL) --target test -t $(TEST_IMAGE) .

test: build-test
	$(PODMAN) run --rm -v "$(PWD)":/app $(TEST_IMAGE)

pipeline: build
	$(PODMAN) run --rm -v "$(PWD)":/app $(IMAGE)

shell: build
	$(PODMAN) run --rm -it -v "$(PWD)":/app --entrypoint /bin/bash $(IMAGE)
