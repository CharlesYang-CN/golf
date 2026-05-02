FROM openmmlab/mmpose:latest

WORKDIR /workspace

RUN pip install --no-cache-dir "runpod~=1.7.6" "trimesh>=4.0.0"

COPY run_golf_3d_whole_image.py /workspace/run_golf_3d_whole_image.py
COPY render_club_from_json.py /workspace/render_club_from_json.py
COPY runpod_handler.py /workspace/runpod_handler.py
COPY test_input.json /workspace/test_input.json

ENV PYTHONUNBUFFERED=1

CMD ["python", "/workspace/runpod_handler.py"]
