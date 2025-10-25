import boto3
from ..startup import bucket_name


s3 = boto3.client("s3")

class AwsServices:

    @staticmethod
    def generate_presigned_photo_upload_url(user_id, size):
        buffer = round(size * 1.05)

        response = s3.generate_presigned_post(
            Bucket=bucket_name,
            Key=f"profile_photos/original/{user_id}/photo",
            Conditions= [["content-length-range", size, buffer], ["starts-with", "$Content-Type", "image/"]],
            ExpiresIn =120
        )
        response["note"] = "Include Content-Type form field (e.g., 'image/jpeg') in your POST request"
        return response

    @staticmethod
    def generate_presigned_photo_download_url(user_id):

        response = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': f"profile_photos/resized/{user_id}/photo"},
            ExpiresIn=60
        )
        return response

    @staticmethod
    def generate_presigned_upload_url(user_id, size, file_name, folder_id = None):
        buffer = round(size * 1.01)
        if  folder_id:
            response = s3.generate_presigned_post(
                Bucket=bucket_name,
                Key=f"files/{user_id}/{folder_id}/{file_name}",
                Conditions=[["content-length-range", size, buffer]],
                ExpiresIn=120
            )
        else:
            response = s3.generate_presigned_post(
                Bucket=bucket_name,
                Key=f"files/{user_id}/{file_name}",
                Conditions=[["content-length-range", size, buffer]],
                ExpiresIn=120
            )
        return response

    @staticmethod
    def generate_presigned_download_url(user_id, file_id, file_name, ext,  folder_id = None):
        filename = f"{file_name}.{ext}"
        if folder_id:
            response = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': f"files/{user_id}/{folder_id}/{file_id}",
                        'ResponseContentDisposition': f'attachment; filename="{filename}"'},
                ExpiresIn=60
            )
        else:
            response = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': f"files/{user_id}/{file_id}",
                        'ResponseContentDisposition': f'attachment; filename="{filename}"'},
                ExpiresIn=60
            )
        return response