import logging


def setup_logging(level=logging.INFO) -> None:
    # Root stays at WARNING so third-party libraries (httpx, huggingface_hub, sentence_transformers,
    # ...) don't drown out the pipeline's own progress lines — only the "candor.*" loggers run at `level`.
    logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s", force=True)
    logging.getLogger("candor").setLevel(level)
