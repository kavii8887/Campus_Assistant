from config.aws_config import textract_client

def extract_tables(image_bytes):
    response = textract_client.analyze_document(
        Document={"Bytes": image_bytes},
        FeatureTypes=["TABLES"]
    )
    return response["Blocks"]
