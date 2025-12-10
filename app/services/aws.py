import boto3


class AwsServices:
    def __init__(self, region_name, bucket_name):
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.s3 = boto3.client("s3", region_name=self.region_name)

    def generate_presigned_photo_upload_url(self, user_id, size):
        buffer = round(size * 1.05)

        response = self.s3.generate_presigned_post(
            Bucket=self.bucket_name,
            Key=f"profile_photos/original/{user_id}/photo",
            Conditions=[
                ["content-length-range", size, buffer],
                ["starts-with", "$Content-Type", "image/"],
            ],
            ExpiresIn=120,
        )
        response["note"] = (
            "Include Content-Type form field (e.g., 'image/jpeg') in your POST request"
        )
        return response

    def generate_presigned_photo_download_url(self, user_id):

        response = self.s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": f"profile_photos/resized/{user_id}/photo",
            },
            ExpiresIn=60,
        )
        return response

    def generate_presigned_upload_url(
        self, user_id, size, file_name, parent_folder_id=None
    ):
        buffer = round(size * 1.01)
        if parent_folder_id:
            response = self.s3.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=f"files/{user_id}/{parent_folder_id}/{file_name}",
                Conditions=[["content-length-range", size, buffer]],
                ExpiresIn=120,
            )
        else:
            response = self.s3.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=f"files/{user_id}/{file_name}",
                Conditions=[["content-length-range", size, buffer]],
                ExpiresIn=120,
            )
        return response

    def generate_presigned_download_url(
        self, user_id, file_id, file_name, folder_id=None
    ):
        filename = f"{file_name}"
        if folder_id:
            response = self.s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": f"files/{user_id}/{folder_id}/{file_id}",
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=60,
            )
        else:
            response = self.s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": f"files/{user_id}/{file_id}",
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=60,
            )
        return response
