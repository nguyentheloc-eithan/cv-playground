#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <iostream>
#include <opencv2/highgui.hpp>
#include <opencv2/videoio.hpp>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>

#include "uavsd/config/engine_config.hpp"
#include "uavsd/engines/registry.hpp"
#include "uavsd/inference/annotator.hpp"
#include "uavsd/inference/frame_source.hpp"

namespace {

struct Options {
    std::string source;
    std::filesystem::path config = "configs/engine.yaml";
    std::optional<std::filesystem::path> output;
    bool show = false;
};

void printUsage(std::string_view program) {
    std::cerr << "Usage: " << program
              << " --source <file|index|url> [--config <yaml>] [--output <video>] [--show]\n";
}

std::optional<Options> parseArgs(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg = argv[i];
        const bool hasValue = i + 1 < argc;
        if (arg == "--source" && hasValue) {
            options.source = argv[++i];
        } else if (arg == "--config" && hasValue) {
            options.config = argv[++i];
        } else if (arg == "--output" && hasValue) {
            options.output = argv[++i];
        } else if (arg == "--show") {
            options.show = true;
        } else {
            return std::nullopt;
        }
    }
    if (options.source.empty()) {
        return std::nullopt;
    }
    return options;
}

std::filesystem::path defaultOutputPath(const std::string& source) {
    const std::filesystem::path path(source);
    const std::string stem = path.has_stem() ? path.stem().string() : "stream";
    return std::filesystem::path("outputs") / (stem + "_annotated.mp4");
}

}  // namespace

int main(int argc, char** argv) {
    const auto options = parseArgs(argc, argv);
    if (!options) {
        printUsage(argv[0]);
        return EXIT_FAILURE;
    }

    try {
        const uavsd::EngineConfig config = uavsd::loadEngineConfig(options->config);
        auto engine = uavsd::createEngine(config);
        engine->load(config.weights);
        engine->warmup();

        uavsd::FrameSource source(options->source);
        const std::filesystem::path outputPath =
            options->output.value_or(defaultOutputPath(options->source));
        if (outputPath.has_parent_path()) {
            std::filesystem::create_directories(outputPath.parent_path());
        }

        const double sourceFps = source.fps();
        cv::VideoWriter writer(outputPath.string(), cv::VideoWriter::fourcc('m', 'p', '4', 'v'),
                               sourceFps > 0.0 ? sourceFps : 30.0, source.frameSize());
        if (!writer.isOpened()) {
            throw std::runtime_error("cannot open output video: " + outputPath.string());
        }

        uavsd::Frame frame;
        std::int64_t frames = 0;
        std::chrono::duration<double, std::milli> detectTime{0.0};
        const auto start = std::chrono::steady_clock::now();

        while (source.read(frame)) {
            const auto detectStart = std::chrono::steady_clock::now();
            const auto detections = engine->detect(frame.image, frame.index, frame.timestamp);
            detectTime += std::chrono::steady_clock::now() - detectStart;
            ++frames;

            uavsd::drawDetections(frame.image, detections);
            writer.write(frame.image);

            if (options->show) {
                cv::imshow("UAVs Defense", frame.image);
                if (cv::waitKey(1) == 'q') {
                    break;
                }
            }
        }

        engine->close();
        const double elapsed =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        const auto frameCount = static_cast<double>(frames);
        std::cout << "engine=" << engine->name() << " frames=" << frames
                  << " avg_detect_ms=" << (frames > 0 ? detectTime.count() / frameCount : 0.0)
                  << " fps=" << (elapsed > 0.0 ? frameCount / elapsed : 0.0)
                  << " output=" << outputPath.string() << '\n';
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
