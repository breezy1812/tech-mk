from app.services.indexing_service import IndexingService


def main() -> None:
    service = IndexingService()
    report = service.reindex()
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()