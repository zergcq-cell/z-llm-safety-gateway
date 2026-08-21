FROM python:3.10-slim

WORKDIR /build

COPY sdk/ ./sdk/
RUN pip install --no-cache-dir grpcio protobuf ./sdk

COPY examples/plugins/python-grpc/ ./plugin/
RUN pip install --no-cache-dir --no-deps ./plugin

EXPOSE 50051

ENTRYPOINT ["python", "-m", "acme_grpc_detector.server"]
CMD ["--port", "50051"]
