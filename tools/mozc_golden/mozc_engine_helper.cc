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
#include "base/clock.h"
#include "base/clock_mock.h"
#include "converter/attribute.h"
#include "converter/converter_interface.h"
#include "converter/inner_segment.h"
#include "converter/segments.h"
#include "data_manager/data_manager.h"
#include "engine/engine.h"
#include "prediction/result.h"
#include "protocol/commands.pb.h"
#include "protocol/config.pb.h"
#include "request/conversion_request.h"

namespace {

constexpr int kMaxCandidates = 20;
constexpr char kFixedTime[] = "2011-04-18T15:06:31Z";

struct Options {
  std::string data_path;
  std::string output_path;
};

struct EngineCase {
  std::string request_type;
  std::string input;
  std::string context;
};

Options ParseOptions(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const std::string data_prefix = "--data=";
    const std::string output_prefix = "--output=";
    if (arg.rfind(data_prefix, 0) == 0) {
      options.data_path = arg.substr(data_prefix.size());
    } else if (arg.rfind(output_prefix, 0) == 0) {
      options.output_path = arg.substr(output_prefix.size());
    }
  }
  if (options.data_path.empty() || options.output_path.empty()) {
    std::cerr << "Usage: mozc_engine_helper --data=/path/mozc.data --output=/path/mozc_kotlin_engine.json\n";
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
      {Attribute::USER_SEGMENT_HISTORY_REWRITER,
       "USER_SEGMENT_HISTORY_REWRITER"},
      {Attribute::KEY_EXPANDED_IN_DICTIONARY,
       "KEY_EXPANDED_IN_DICTIONARY"},
      {Attribute::NO_DELETABLE, "NO_DELETABLE"},
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

std::string CategoryName(mozc::converter::Candidate::Category category) {
  switch (category) {
    case mozc::converter::Candidate::DEFAULT_CATEGORY:
      return "DEFAULT_CATEGORY";
    case mozc::converter::Candidate::SYMBOL:
      return "SYMBOL";
    case mozc::converter::Candidate::OTHER:
      return "OTHER";
  }
  return "DEFAULT_CATEGORY";
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

void WriteInnerSegments(std::ostream& out,
                        const mozc::converter::Candidate& candidate,
                        const std::string& pad) {
  out << pad << "\"innerSegments\": [";
  if (!candidate.inner_segment_boundary.empty()) {
    out << "\n";
    size_t index = 0;
    for (const auto& inner : candidate.inner_segments()) {
      out << pad << "  {\n";
      out << pad << "    \"index\": " << index << ",\n";
      out << pad << "    \"key\": " << JsonString(inner.GetKey()) << ",\n";
      out << pad << "    \"value\": " << JsonString(inner.GetValue()) << ",\n";
      out << pad << "    \"contentKey\": " << JsonString(inner.GetContentKey()) << ",\n";
      out << pad << "    \"contentValue\": " << JsonString(inner.GetContentValue()) << "\n";
      out << pad << "  }";
      ++index;
      if (index != candidate.inner_segment_boundary.size()) {
        out << ",";
      }
      out << "\n";
    }
    out << pad;
  }
  out << "]";
}

void WriteCandidate(std::ostream& out,
                    const mozc::converter::Candidate& candidate,
                    size_t index, const std::string& pad) {
  const uint32_t types =
      candidate.attributes & mozc::prediction::kPredictionTypesMaskForTesting;
  const uint32_t attributes =
      candidate.attributes & ~mozc::prediction::kPredictionTypesMaskForTesting;
  out << pad << "{\n";
  out << pad << "  \"index\": " << index << ",\n";
  out << pad << "  \"key\": " << JsonString(candidate.key) << ",\n";
  out << pad << "  \"value\": " << JsonString(candidate.value) << ",\n";
  out << pad << "  \"contentKey\": " << JsonString(candidate.content_key) << ",\n";
  out << pad << "  \"contentValue\": " << JsonString(candidate.content_value) << ",\n";
  out << pad << "  \"cost\": " << candidate.cost << ",\n";
  out << pad << "  \"wcost\": " << candidate.wcost << ",\n";
  out << pad << "  \"structureCost\": " << candidate.structure_cost << ",\n";
  out << pad << "  \"lid\": " << candidate.lid << ",\n";
  out << pad << "  \"rid\": " << candidate.rid << ",\n";
  out << pad << "  \"attributes\": ";
  WriteStringArray(out, AttributeNames(attributes));
  out << ",\n";
  out << pad << "  \"description\": " << JsonString(candidate.description) << ",\n";
  out << pad << "  \"category\": " << JsonString(CategoryName(candidate.category)) << ",\n";
  WriteInnerSegments(out, candidate, pad + "  ");
  out << ",\n";
  out << pad << "  \"source\": \"\",\n";
  out << pad << "  \"types\": ";
  WriteStringArray(out, PredictionTypeNames(types));
  out << ",\n";
  out << pad << "  \"consumedKeySize\": " << candidate.consumed_key_size << "\n";
  out << pad << "}";
}

void WriteSegments(std::ostream& out, const mozc::Segments& segments) {
  out << "      \"segments\": [\n";
  for (size_t i = 0; i < segments.conversion_segments_size(); ++i) {
    const mozc::Segment& segment = segments.conversion_segment(i);
    out << "        {\n";
    out << "          \"index\": " << i << ",\n";
    out << "          \"key\": " << JsonString(segment.key()) << ",\n";
    out << "          \"candidates\": [\n";
    for (size_t j = 0; j < segment.candidates_size(); ++j) {
      WriteCandidate(out, segment.candidate(j), j, "            ");
      if (j + 1 != segment.candidates_size()) {
        out << ",";
      }
      out << "\n";
    }
    out << "          ]\n";
    out << "        }";
    if (i + 1 != segments.conversion_segments_size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "      ]\n";
}

mozc::ConversionRequest BuildRequest(
    absl::string_view input,
    mozc::ConversionRequest::RequestType request_type,
    bool mixed_conversion,
    bool zero_query_suggestion) {
  mozc::commands::Request request;
  request.set_zero_query_suggestion(zero_query_suggestion);
  request.set_mixed_conversion(mixed_conversion);
  request.set_candidates_size_limit(kMaxCandidates);

  mozc::config::Config config;
  config.set_use_spelling_correction(true);
  config.set_use_zip_code_conversion(true);
  config.set_use_t13n_conversion(true);
  config.set_use_single_kanji_conversion(true);
  config.set_use_symbol_conversion(true);
  config.set_use_number_conversion(true);
  config.set_use_emoticon_conversion(true);
  config.set_use_emoji_conversion(true);
  config.set_suggestions_size(3);

  mozc::ConversionRequest::Options options;
  options.request_type = request_type;
  options.max_conversion_candidates_size = kMaxCandidates;
  options.use_zip_code_conversion = true;
  options.use_t13n_conversion = true;

  return mozc::ConversionRequestBuilder()
      .SetRequest(request)
      .SetConfig(config)
      .SetOptions(options)
      .SetKey(input)
      .Build();
}

void AddHistorySegment(mozc::Segments* segments, absl::string_view context) {
  mozc::Segment* segment = segments->add_segment();
  segment->set_key(context);
  segment->set_segment_type(mozc::Segment::HISTORY);
  mozc::converter::Candidate* candidate = segment->add_candidate();
  candidate->key = std::string(context);
  candidate->value = std::string(context);
  candidate->content_key = std::string(context);
  candidate->content_value = std::string(context);
  candidate->attributes = mozc::converter::Attribute::NO_LEARNING;
}

std::vector<EngineCase> BuildCases() {
  std::vector<EngineCase> cases;
  for (const std::string& input : {
           "へんかん", "きょう", "ありがとう", "とうきょう",
           "にほんご", "わたしは", "これは", "かんじ",
           "やまだたろう", "123", "第一", "〒1000001",
       }) {
    cases.push_back({"CONVERSION", input, ""});
  }
  for (const std::string& input : {
           "きょ", "きょう", "ありが", "ありがとう",
           "とうき", "とうきょう", "にほ", "にほん",
           "にほんご", "わた", "わたし", "123",
       }) {
    cases.push_back({"PREDICTION", input, ""});
  }
  for (const std::string& input : {
           "あり", "ありが", "きょ", "とうき", "にほ", "わた",
       }) {
    cases.push_back({"SUGGESTION", input, ""});
  }
  for (const std::string& context : {
           "ありがとう", "おはよう", "こんにちは", "こんばんは", "よろしく",
       }) {
    cases.push_back({"ZERO_QUERY", context, context});
  }
  for (const std::string& input : {
           "変換", "今日", "日本語", "東京",
       }) {
    cases.push_back({"REVERSE", input, ""});
  }
  return cases;
}

bool EvaluateCase(const mozc::ConverterInterface& converter,
                  const EngineCase& engine_case, mozc::Segments* segments) {
  if (engine_case.request_type == "CONVERSION") {
    const mozc::ConversionRequest request = BuildRequest(
        engine_case.input, mozc::ConversionRequest::CONVERSION, false, false);
    return converter.StartConversion(request, segments);
  }
  if (engine_case.request_type == "PREDICTION") {
    const mozc::ConversionRequest request = BuildRequest(
        engine_case.input, mozc::ConversionRequest::PREDICTION, false, false);
    return converter.StartPrediction(request, segments);
  }
  if (engine_case.request_type == "SUGGESTION") {
    const mozc::ConversionRequest request = BuildRequest(
        engine_case.input, mozc::ConversionRequest::SUGGESTION, false, false);
    return converter.StartPrediction(request, segments);
  }
  if (engine_case.request_type == "ZERO_QUERY") {
    AddHistorySegment(segments, engine_case.context);
    const mozc::ConversionRequest request =
        BuildRequest("", mozc::ConversionRequest::PREDICTION, true, true);
    return converter.StartPrediction(request, segments);
  }
  if (engine_case.request_type == "REVERSE") {
    return converter.StartReverseConversion(segments, engine_case.input);
  }
  std::cerr << "Unknown request type: " << engine_case.request_type << "\n";
  return false;
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
  absl::StatusOr<std::unique_ptr<mozc::Engine>> engine =
      mozc::Engine::CreateEngine(std::move(data_manager).value());
  if (!engine.ok()) {
    std::cerr << engine.status() << "\n";
    return 1;
  }

  mozc::ClockMock clock(mozc::ParseTimeOrDie(kFixedTime));
  mozc::Clock::SetClockForUnitTest(&clock);

  const std::shared_ptr<const mozc::ConverterInterface> converter =
      (*engine)->GetConverter();
  const std::vector<EngineCase> cases = BuildCases();

  std::ofstream out(options.output_path);
  if (!out) {
    std::cerr << "Cannot open output: " << options.output_path << "\n";
    mozc::Clock::SetClockForUnitTest(nullptr);
    return 1;
  }

  out << "{\n";
  out << "  \"engineDataVersion\": "
      << JsonString((*engine)->GetDataVersion()) << ",\n";
  out << "  \"fixedTime\": " << JsonString(kFixedTime) << ",\n";
  out << "  \"cases\": [\n";
  for (size_t i = 0; i < cases.size(); ++i) {
    const EngineCase& engine_case = cases[i];
    mozc::Segments segments;
    if (!EvaluateCase(*converter, engine_case, &segments)) {
      std::cerr << "Engine conversion failed: requestType="
                << engine_case.request_type << " input=" << engine_case.input
                << " context=" << engine_case.context << "\n";
      mozc::Clock::SetClockForUnitTest(nullptr);
      return 1;
    }
    out << "    {\n";
    out << "      \"requestType\": " << JsonString(engine_case.request_type) << ",\n";
    out << "      \"input\": " << JsonString(engine_case.input) << ",\n";
    out << "      \"context\": " << JsonString(engine_case.context) << ",\n";
    WriteSegments(out, segments);
    out << "    }";
    if (i + 1 != cases.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ]\n";
  out << "}\n";

  mozc::Clock::SetClockForUnitTest(nullptr);
  return 0;
}
