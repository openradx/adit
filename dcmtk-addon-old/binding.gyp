{
    "targets": [
        {
            "target_name": "testaddon",
            "cflags!": ["-fno-exceptions"],
            "cflags_cc!": ["-fno-exceptions"],
            "sources": ["cppsrc/main.cpp"],
            "include_dirs": [
                "<!@(node -p \"require('node-addon-api').include\")",
                "/workspace/dcmtk-3.6.7-install/usr/local/include",
                "/workspace/adit/dcmtk/includes",
            ],
            "libraries": ["/workspace/adit/dcmtk/build/libconnector.so"],
            "dependencies": ["<!(node -p \"require('node-addon-api').gyp\")"],
            "defines": ["NAPI_DISABLE_CPP_EXCEPTIONS"],
        }
    ]
}
