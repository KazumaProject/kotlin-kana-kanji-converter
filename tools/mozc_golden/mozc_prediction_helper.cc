#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "absl/status/statusor.h"
#include "absl/strings/string_view.h"
#include "converter/attribute.h"
#include "converter/converter_interface.h"
#include "converter/immutable_converter.h"
#include "converter/segments.h"
#include "data_manager/data_manager.h"
#include "engine/modules.h"
#include "prediction/predictor.h"
#include "prediction/result.h"
#include "protocol/commands.pb.h"
#include "protocol/config.pb.h"
#include "request/conversion_request.h"

namespace {

struct Options {
  std::string data_path;
  std::string predictor_output_path;
  std::string zero_query_output_path;
};

class NoActualConverter final : public mozc::ConverterInterface {
 public:
  bool StartConversion(const mozc::ConversionRequest& request,
                       mozc::Segments* segments) const override {
    return false;
  }

  bool StartReverseConversion(mozc::Segments* segments,
                              absl::string_view key) const override {
    return false;
  }

  bool StartPrediction(const mozc::ConversionRequest& request,
                       mozc::Segments* segments) const override {
    return false;
  }

  bool StartPredictionWithPreviousSuggestion(
      const mozc::ConversionRequest& request,
      const mozc::Segment& previous_segment,
      mozc::Segments* segments) const override {
    return false;
  }

  void PrependCandidates(const mozc::ConversionRequest& request,
                         const mozc::Segment& segment,
                         mozc::Segments* segments) const override {}

  void FinishConversion(const mozc::ConversionRequest& request,
                        mozc::Segments* segments) const override {}

  void CancelConversion(mozc::Segments* segments) const override {}

  void ResetConversion(mozc::Segments* segments) const override {}

  void RevertConversion(mozc::Segments* segments) const override {}

  bool DeleteCandidateFromHistory(const mozc::Segments& segments,
                                  size_t segment_index,
                                  int candidate_index) const override {
    return false;
  }

  bool ReconstructHistory(mozc::Segments* segments,
                          absl::string_view preceding_text) const override {
    return false;
  }

  bool CommitSegmentValue(mozc::Segments* segments, size_t segment_index,
                          int candidate_index) const override {
    return false;
  }

  bool CommitPartialSuggestionSegmentValue(
      mozc::Segments* segments, size_t segment_index, int candidate_index,
      absl::string_view current_segment_key,
      absl::string_view new_segment_key) const override {
    return false;
  }

  bool FocusSegmentValue(mozc::Segments* segments, size_t segment_index,
                         int candidate_index) const override {
    return false;
  }

  bool CommitSegments(
      mozc::Segments* segments,
      absl::Span<const size_t> candidate_index) const override {
    return false;
  }

  bool ResizeSegment(mozc::Segments* segments,
                     const mozc::ConversionRequest& request,
                     size_t segment_index, int offset_length) const override {
    return false;
  }

  bool ResizeSegments(mozc::Segments* segments,
                      const mozc::ConversionRequest& request,
                      size_t start_segment_index,
                      absl::Span<const uint8_t> new_size_array) const override {
    return false;
  }

  void CommitContext(const mozc::ConversionRequest& request) const override {}
};

Options ParseOptions(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const std::string data_prefix = "--data=";
    const std::string predictor_prefix = "--predictor_output=";
    const std::string zero_query_prefix = "--zero_query_output=";
    if (arg.rfind(data_prefix, 0) == 0) {
      options.data_path = arg.substr(data_prefix.size());
    } else if (arg.rfind(predictor_prefix, 0) == 0) {
      options.predictor_output_path = arg.substr(predictor_prefix.size());
    } else if (arg.rfind(zero_query_prefix, 0) == 0) {
      options.zero_query_output_path = arg.substr(zero_query_prefix.size());
    }
  }
  if (options.data_path.empty() || options.predictor_output_path.empty() ||
      options.zero_query_output_path.empty()) {
    std::cerr << "Usage: mozc_prediction_helper --data=/path/mozc.data --predictor_output=/path/predictor.json --zero_query_output=/path/zero_query.json\n";
    std::exit(2);
  }
  return options;
}

std::string JsonString(std::string_view value) {
  std::string out = "\"";
  for (const unsigned char ch : value) {
    switch (ch) {
      case '\\':
        out += "\\\\";
        break;
      case '"':
        out += "\\\"";
        break;
      case '\b':
        out += "\\b";
        break;
      case '\f':
        out += "\\f";
        break;
      case '\n':
        out += "\\n";
        break;
      case '\r':
        out += "\\r";
        break;
      case '\t':
        out += "\\t";
        break;
      default:
        if (ch < 0x20) {
          constexpr char hex[] = "0123456789ABCDEF";
          out += "\\u00";
          out += hex[ch >> 4];
          out += hex[ch & 0x0F];
        } else {
          out.push_back(static_cast<char>(ch));
        }
    }
  }
  out += "\"";
  return out;
}

std::vector<std::string> AttributeNames(uint32_t attributes) {
  using mozc::converter::Attribute;
  const std::vector<std::pair<uint32_t, std::string>> names = {
      {Attribute::BEST_CANDIDATE, "BEST_CANDIDATE"},
      {Attribute::RERANKED, "RERANKED"},
      {Attribute::NO_HISTORY_LEARNING, "NO_HISTORY_LEARNING"},
      {Attribute::NO_SUGGEST_LEARNING, "NO_SUGGEST_LEARNING"},
      {Attribute::CONTEXT_SENSITIVE, "CONTEXT_SENSITIVE"},
      {Attribute::SPELLING_CORRECTION, "SPELLING_CORRECTION"},
      {Attribute::NO_VARIANTS_EXPANSION, "NO_VARIANTS_EXPANSION"},
      {Attribute::NO_EXTRA_DESCRIPTION, "NO_EXTRA_DESCRIPTION"},
      {Attribute::REALTIME_CONVERSION, "REALTIME_CONVERSION"},
      {Attribute::USER_DICTIONARY, "USER_DICTIONARY"},
      {Attribute::COMMAND_CANDIDATE, "COMMAND_CANDIDATE"},
      {Attribute::PARTIALLY_KEY_CONSUMED, "PARTIALLY_KEY_CONSUMED"},
      {Attribute::TYPING_CORRECTION, "TYPING_CORRECTION"},
      {Attribute::AUTO_PARTIAL_SUGGESTION, "AUTO_PARTIAL_SUGGESTION"},
      {Attribute::USER_HISTORY_PREDICTION, "USER_HISTORY_PREDICTION"},
      {Attribute::SUFFIX_DICTIONARY, "SUFFIX_DICTIONARY"},
      {Attribute::NO_MODIFICATION, "NO_MODIFICATION"},
      {Attribute::USER_SEGMENT_HISTORY_REWRITER, "USER_SEGMENT_HISTORY_REWRITER"},
      {Attribute::KEY_EXPANDED_IN_DICTIONARY, "KEY_EXPANDED_IN_DICTIONARY"},
      {Attribute::NO_DELETABLE, "NO_DELETABLE"},
      {Attribute::UNIGRAM, "UNIGRAM"},
      {Attribute::BIGRAM, "BIGRAM"},
      {Attribute::ENGLISH, "ENGLISH"},
      {Attribute::NUMBER, "NUMBER"},
      {Attribute::SINGLE_KANJI, "SINGLE_KANJI"},
      {Attribute::TYPING_COMPLETION, "TYPING_COMPLETION"},
      {Attribute::POST_CORRECTION, "POST_CORRECTION"},
      {Attribute::SUPPLEMENTAL_MODEL, "SUPPLEMENTAL_MODEL"},
      {Attribute::WEAK_USER_HISTORY_PREDICTION, "WEAK_USER_HISTORY_PREDICTION"},
      {Attribute::REALTIME_TOP, "REALTIME_TOP"},
      {Attribute::DISABLE_RESCORING, "DISABLE_RESCORING"},
  };
  std::vector<std::string> result;
  for (const auto& [bit, name] : names) {
    if (attributes & bit) {
      result.push_back(name);
    }
  }
  return result;
}

std::vector<std::string> PredictionTypeNames(uint32_t types) {
  using mozc::prediction::PredictionType;
  const std::vector<std::pair<uint32_t, std::string>> names = {
      {PredictionType::UNIGRAM, "UNIGRAM"},
      {PredictionType::BIGRAM, "BIGRAM"},
      {PredictionType::REALTIME, "REALTIME"},
      {PredictionType::SUFFIX, "SUFFIX"},
      {PredictionType::ENGLISH, "ENGLISH"},
      {PredictionType::TYPING_CORRECTION, "TYPING_CORRECTION"},
      {PredictionType::PREFIX, "PREFIX"},
      {PredictionType::NUMBER, "NUMBER"},
      {PredictionType::SINGLE_KANJI, "SINGLE_KANJI"},
      {PredictionType::TYPING_COMPLETION, "TYPING_COMPLETION"},
      {PredictionType::POST_CORRECTION, "POST_CORRECTION"},
      {PredictionType::SUPPLEMENTAL_MODEL, "SUPPLEMENTAL_MODEL"},
      {PredictionType::WEAK_USER_HISTORY_PREDICTION,
       "WEAK_USER_HISTORY_PREDICTION"},
      {PredictionType::REALTIME_TOP, "REALTIME_TOP"},
      {PredictionType::KEY_EXPANDED_IN_DICTIONARY,
       "KEY_EXPANDED_IN_DICTIONARY"},
      {PredictionType::DISABLE_RESCORING, "DISABLE_RESCORING"},
  };
  std::vector<std::string> result;
  for (const auto& [bit, name] : names) {
    if (types & bit) {
      result.push_back(name);
    }
  }
  return result;
}

void WriteStringArray(std::ostream& out, const std::vector<std::string>& values) {
  out << "[";
  for (size_t i = 0; i < values.size(); ++i) {
    if (i != 0) {
      out << ", ";
    }
    out << JsonString(values[i]);
  }
  out << "]";
}

void WriteResult(std::ostream& out, const mozc::prediction::Result& result,
                 size_t index, const std::string& pad) {
  const uint32_t types = result.GetPredictionTypesForTesting();
  const uint32_t attributes =
      result.attributes & ~mozc::prediction::kPredictionTypesMaskForTesting;
  out << pad << "{\n";
  out << pad << "  \"index\": " << index << ",\n";
  out << pad << "  \"key\": " << JsonString(result.key) << ",\n";
  out << pad << "  \"value\": " << JsonString(result.value) << ",\n";
  out << pad << "  \"contentKey\": " << JsonString(result.key) << ",\n";
  out << pad << "  \"contentValue\": " << JsonString(result.value) << ",\n";
  out << pad << "  \"cost\": " << result.cost << ",\n";
  out << pad << "  \"wcost\": " << result.wcost << ",\n";
  out << pad << "  \"structureCost\": 0,\n";
  out << pad << "  \"lid\": " << result.lid << ",\n";
  out << pad << "  \"rid\": " << result.rid << ",\n";
  out << pad << "  \"attributes\": ";
  WriteStringArray(out, AttributeNames(attributes));
  out << ",\n";
  out << pad << "  \"types\": ";
  WriteStringArray(out, PredictionTypeNames(types));
  out << ",\n";
  out << pad << "  \"candidateSource\": \"\",\n";
  out << pad << "  \"consumedKeySize\": " << result.consumed_key_size << "\n";
  out << pad << "}";
}

mozc::ConversionRequest BuildPredictionRequest(absl::string_view input) {
  mozc::commands::Request request;
  mozc::config::Config config;
  mozc::ConversionRequest::Options options;
  options.request_type = mozc::ConversionRequest::PREDICTION;
  return mozc::ConversionRequestBuilder()
      .SetRequest(request)
      .SetConfig(config)
      .SetOptions(options)
      .SetKey(input)
      .Build();
}

mozc::ConversionRequest BuildZeroQueryRequest(absl::string_view context) {
  mozc::commands::Request request;
  request.set_zero_query_suggestion(true);
  request.set_mixed_conversion(true);

  mozc::config::Config config;
  mozc::prediction::Result history;
  history.key = std::string(context);
  history.value = std::string(context);

  mozc::ConversionRequest::Options options;
  options.request_type = mozc::ConversionRequest::PREDICTION;
  return mozc::ConversionRequestBuilder()
      .SetRequest(request)
      .SetConfig(config)
      .SetHistoryResult(history)
      .SetOptions(options)
      .Build();
}

void WritePredictorFixture(const std::string& output_path,
                           std::string_view version,
                           const mozc::prediction::Predictor& predictor) {
  const std::vector<std::string> inputs = {
      "きょ",       "きょう", "ありが", "ありがとう",
      "とうき",     "とうきょう", "にほ",   "にほん",
      "にほんご",   "わた",   "わたし", "123",
  };

  std::ofstream out(output_path);
  if (!out) {
    std::cerr << "Cannot open predictor output: " << output_path << "\n";
    std::exit(1);
  }
  out << "{\n";
  out << "  \"engineDataVersion\": " << JsonString(version) << ",\n";
  out << "  \"cases\": [\n";
  for (size_t i = 0; i < inputs.size(); ++i) {
    const mozc::ConversionRequest request = BuildPredictionRequest(inputs[i]);
    const std::vector<mozc::prediction::Result> results =
        predictor.Predict(request);
    out << "    {\n";
    out << "      \"input\": " << JsonString(inputs[i]) << ",\n";
    out << "      \"requestType\": \"PREDICTION\",\n";
    out << "      \"results\": [\n";
    for (size_t j = 0; j < results.size(); ++j) {
      WriteResult(out, results[j], j, "        ");
      if (j + 1 != results.size()) {
        out << ",";
      }
      out << "\n";
    }
    out << "      ]\n";
    out << "    }";
    if (i + 1 != inputs.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ]\n";
  out << "}\n";
}

void WriteZeroQueryFixture(const std::string& output_path,
                           std::string_view version,
                           const mozc::prediction::Predictor& predictor) {
  const std::vector<std::string> contexts = {
      "ありがとう", "おはよう", "こんにちは", "こんばんは", "よろしく",
  };

  std::ofstream out(output_path);
  if (!out) {
    std::cerr << "Cannot open zero query output: " << output_path << "\n";
    std::exit(1);
  }
  out << "{\n";
  out << "  \"engineDataVersion\": " << JsonString(version) << ",\n";
  out << "  \"cases\": [\n";
  for (size_t i = 0; i < contexts.size(); ++i) {
    const mozc::ConversionRequest request = BuildZeroQueryRequest(contexts[i]);
    const std::vector<mozc::prediction::Result> results =
        predictor.Predict(request);
    out << "    {\n";
    out << "      \"context\": " << JsonString(contexts[i]) << ",\n";
    out << "      \"results\": [\n";
    for (size_t j = 0; j < results.size(); ++j) {
      WriteResult(out, results[j], j, "        ");
      if (j + 1 != results.size()) {
        out << ",";
      }
      out << "\n";
    }
    out << "      ]\n";
    out << "    }";
    if (i + 1 != contexts.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ]\n";
  out << "}\n";
}

}  // namespace

int main(int argc, char** argv) {
  const Options options = ParseOptions(argc, argv);
  absl::StatusOr<std::unique_ptr<const mozc::DataManager>> data_manager =
      mozc::DataManager::CreateFromFile(
          options.data_path, mozc::DataManager::GetDataSetMagicNumber("oss"));
  if (!data_manager.ok()) {
    std::cerr << data_manager.status() << "\n";
    return 1;
  }
  absl::StatusOr<std::unique_ptr<mozc::engine::Modules>> modules =
      mozc::engine::Modules::Create(std::move(data_manager).value());
  if (!modules.ok()) {
    std::cerr << modules.status() << "\n";
    return 1;
  }

  mozc::ImmutableConverter immutable_converter(**modules);
  NoActualConverter converter;
  mozc::prediction::Predictor predictor(**modules, converter,
                                        immutable_converter);
  const absl::string_view version_view =
      (*modules)->GetDataManager().GetDataVersion();
  const std::string version(version_view.data(), version_view.size());

  WritePredictorFixture(options.predictor_output_path, version, predictor);
  WriteZeroQueryFixture(options.zero_query_output_path, version, predictor);
  return 0;
}
