python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/auth.proto
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/llm.proto
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. protos/raft.proto