#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "absl/status/statusor.h"
#include "base/clock.h"
#include "base/clock_mock.h"
#include "converter/attribute.h"
#include "converter/immutable_converter.h"
#include "converter/inner_segment.h"
#include "converter/lattice.h"
#include "converter/segments.h"
#include "data_manager/data_manager.h"
#include "engine/modules.h"
#include "protocol/commands.pb.h"
#include "protocol/config.pb.h"
#include "request/conversion_request.h"
#include "request/options.h"
#include "rewriter/rewriter.h"

namespace {

struct Options {
  std::string data_path;
  std::string output_path;
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
    std::cerr << "Usage: mozc_rewriter_helper --data=/path/mozc.data --output=/path/rewriter.json\n";
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
      {Attribute::WEAK_USER_HISTORY_PREDICTION,
       "WEAK_USER_HISTORY_PREDICTION"},
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

void WriteStringArray(std::ostream& out,
                      const std::vector<std::string>& values) {
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
      out << pad << "    \"contentKey\": " << JsonString(inner.GetContentKey())
          << ",\n";
      out << pad << "    \"contentValue\": "
          << JsonString(inner.GetContentValue()) << "\n";
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
                    const mozc::converter::Candidate& candidate, size_t index,
                    const std::string& pad) {
  out << pad << "{\n";
  out << pad << "  \"index\": " << index << ",\n";
  out << pad << "  \"key\": " << JsonString(candidate.key) << ",\n";
  out << pad << "  \"value\": " << JsonString(candidate.value) << ",\n";
  out << pad << "  \"contentKey\": " << JsonString(candidate.content_key)
      << ",\n";
  out << pad << "  \"contentValue\": " << JsonString(candidate.content_value)
      << ",\n";
  out << pad << "  \"cost\": " << candidate.cost << ",\n";
  out << pad << "  \"wcost\": " << candidate.wcost << ",\n";
  out << pad << "  \"structureCost\": " << candidate.structure_cost << ",\n";
  out << pad << "  \"lid\": " << candidate.lid << ",\n";
  out << pad << "  \"rid\": " << candidate.rid << ",\n";
  out << pad << "  \"attributes\": ";
  WriteStringArray(out, AttributeNames(candidate.attributes));
  out << ",\n";
  out << pad << "  \"consumedKeySize\": " << candidate.consumed_key_size
      << ",\n";
  out << pad << "  \"description\": " << JsonString(candidate.description)
      << ",\n";
  out << pad << "  \"category\": " << JsonString(CategoryName(candidate.category))
      << ",\n";
  WriteInnerSegments(out, candidate, pad + "  ");
  out << "\n";
  out << pad << "}";
}

void WriteCandidateArray(std::ostream& out, const mozc::Segments& segments,
                         const char* name, const std::string& pad) {
  out << pad << JsonString(name) << ": [\n";
  size_t flat_index = 0;
  for (size_t segment_index = 0;
       segment_index < segments.conversion_segments_size(); ++segment_index) {
    const mozc::Segment& segment = segments.conversion_segment(segment_index);
    for (size_t candidate_index = 0; candidate_index < segment.candidates_size();
         ++candidate_index) {
      if (flat_index != 0) {
        out << ",\n";
      }
      WriteCandidate(out, segment.candidate(candidate_index), flat_index,
                     pad + "  ");
      ++flat_index;
    }
  }
  if (flat_index != 0) {
    out << "\n";
  }
  out << pad << "]";
}

mozc::ConversionRequest BuildConversionRequest(const std::string& input) {
  mozc::commands::Request request;
  request.set_mixed_conversion(false);
  request.set_emoji_rewriter_capability(mozc::RewriterInterface::CONVERSION);

  mozc::config::Config config;
  config.set_use_single_kanji_conversion(true);
  config.set_use_symbol_conversion(true);
  config.set_use_number_conversion(true);
  config.set_use_emoticon_conversion(true);
  config.set_use_emoji_conversion(true);

  mozc::ConversionRequest::Options options;
  options.request_type = mozc::ConversionRequest::CONVERSION;
  options.max_conversion_candidates_size = 20;
  options.use_zip_code_conversion = true;
  options.use_t13n_conversion = true;

  return mozc::ConversionRequestBuilder()
      .SetRequest(request)
      .SetConfig(config)
      .SetOptions(options)
      .SetKey(input)
      .Build();
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

  mozc::ClockMock clock(mozc::ParseTimeOrDie("2011-04-18T15:06:31Z"));
  mozc::Clock::SetClockForUnitTest(&clock);

  mozc::ImmutableConverter converter(**modules);
  mozc::Rewriter rewriter(**modules);
  const std::vector<std::string> inputs = {
      "きょう",       "あした",   "きのう",   "ありがとう",
      "とうきょう",   "にほんご", "かんじ",   "やまだたろう",
      "123",          "１２３",   "だい一",   ":)",
      "〒1000001",    "きごう",   "みぎ",     "ひと",
  };

  std::ofstream out(options.output_path);
  if (!out) {
    std::cerr << "Cannot open output: " << options.output_path << "\n";
    mozc::Clock::SetClockForUnitTest(nullptr);
    return 1;
  }

  out << "{\n";
  out << "  \"engineDataVersion\": "
      << JsonString((*modules)->GetDataManager().GetDataVersion()) << ",\n";
  out << "  \"fixedTime\": \"2011-04-18T15:06:31Z\",\n";
  out << "  \"cases\": [\n";
  for (size_t i = 0; i < inputs.size(); ++i) {
    const mozc::ConversionRequest request = BuildConversionRequest(inputs[i]);
    mozc::Segments segments;
    mozc::Lattice lattice;
    segments.InitForConvert(inputs[i]);
    if (!converter.Convert(request.options(), &segments, &lattice)) {
      std::cerr << "ImmutableConverter failed for input: " << inputs[i] << "\n";
      mozc::Clock::SetClockForUnitTest(nullptr);
      return 1;
    }
    const mozc::Segments before_segments = segments;
    rewriter.Rewrite(request, &segments);

    out << "    {\n";
    out << "      \"input\": " << JsonString(inputs[i]) << ",\n";
    out << "      \"requestType\": \"CONVERSION\",\n";
    WriteCandidateArray(out, before_segments, "beforeRewrite", "      ");
    out << ",\n";
    WriteCandidateArray(out, segments, "afterRewrite", "      ");
    out << "\n";
    out << "    }";
    if (i + 1 != inputs.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ]\n";
  out << "}\n";

  mozc::Clock::SetClockForUnitTest(nullptr);
  return 0;
}
