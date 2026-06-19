#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "absl/status/statusor.h"
#include "converter/attribute.h"
#include "converter/candidate_filter.h"
#include "converter/immutable_converter.h"
#include "converter/inner_segment.h"
#include "converter/lattice.h"
#include "converter/node.h"
#include "converter/segments.h"
#include "data_manager/data_manager.h"
#include "engine/modules.h"
#include "request/options.h"

namespace {

struct Options {
  std::string data_path;
  std::string nbest_output_path;
  std::string candidate_filter_output_path;
};

Options ParseOptions(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const std::string data_prefix = "--data=";
    const std::string nbest_prefix = "--nbest_output=";
    const std::string filter_prefix = "--candidate_filter_output=";
    if (arg.rfind(data_prefix, 0) == 0) {
      options.data_path = arg.substr(data_prefix.size());
    } else if (arg.rfind(nbest_prefix, 0) == 0) {
      options.nbest_output_path = arg.substr(nbest_prefix.size());
    } else if (arg.rfind(filter_prefix, 0) == 0) {
      options.candidate_filter_output_path = arg.substr(filter_prefix.size());
    }
  }
  if (options.data_path.empty() || options.nbest_output_path.empty() ||
      options.candidate_filter_output_path.empty()) {
    std::cerr << "Usage: mozc_nbest_candidate_filter_helper --data=/path/mozc.data --nbest_output=/path/nbest_generator.json --candidate_filter_output=/path/candidate_filter.json\n";
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
  WriteStringArray(out, AttributeNames(candidate.attributes));
  out << ",\n";
  WriteInnerSegments(out, candidate, pad + "  ");
  out << "\n";
  out << pad << "}";
}

void WriteFilterCandidate(std::ostream& out,
                          const mozc::converter::Candidate& candidate,
                          const std::string& pad) {
  out << pad << "{\n";
  out << pad << "  \"key\": " << JsonString(candidate.key) << ",\n";
  out << pad << "  \"value\": " << JsonString(candidate.value) << ",\n";
  out << pad << "  \"lid\": " << candidate.lid << ",\n";
  out << pad << "  \"rid\": " << candidate.rid << ",\n";
  out << pad << "  \"cost\": " << candidate.cost << ",\n";
  out << pad << "  \"attributes\": ";
  WriteStringArray(out, AttributeNames(candidate.attributes));
  out << "\n";
  out << pad << "}";
}

std::vector<mozc::converter::Candidate> FlattenCandidates(
    const mozc::Segments& segments) {
  std::vector<mozc::converter::Candidate> result;
  for (size_t i = 0; i < segments.conversion_segments_size(); ++i) {
    const mozc::Segment& segment = segments.conversion_segment(i);
    for (size_t j = 0; j < segment.candidates_size(); ++j) {
      result.push_back(segment.candidate(j));
    }
  }
  return result;
}

std::vector<mozc::converter::Candidate> BuildBeforeFilter(
    const std::vector<mozc::converter::Candidate>& candidates) {
  std::vector<mozc::converter::Candidate> result;
  for (const mozc::converter::Candidate& candidate : candidates) {
    result.push_back(candidate);
    result.push_back(candidate);
  }
  return result;
}

std::vector<mozc::converter::Candidate> ApplyOfficialCandidateFilter(
    const mozc::engine::Modules& modules, const std::string& input,
    const std::vector<mozc::converter::Candidate>& before) {
  mozc::converter::CandidateFilter filter(
      modules.GetUserDictionary(), modules.GetPosMatcher(),
      modules.GetSuggestionFilter());
  mozc::ConversionOptions conversion_options;
  conversion_options.request_type = mozc::RequestType::CONVERSION;

  std::vector<mozc::converter::Candidate> after;
  for (const mozc::converter::Candidate& candidate : before) {
    mozc::Node node;
    node.Init();
    node.key = candidate.key;
    node.value = candidate.value;
    node.lid = candidate.lid;
    node.rid = candidate.rid;
    node.wcost = candidate.wcost;
    node.cost = candidate.cost;
    const std::vector<const mozc::Node*> nodes = {&node};
    const mozc::converter::CandidateFilter::ResultType result =
        filter.FilterCandidate(conversion_options, input, &candidate, nodes,
                               nodes);
    if (result == mozc::converter::CandidateFilter::GOOD_CANDIDATE) {
      after.push_back(candidate);
    } else if (result ==
               mozc::converter::CandidateFilter::STOP_ENUMERATION) {
      break;
    }
  }
  return after;
}

void WriteNBestFixture(const std::string& output_path,
                       const mozc::engine::Modules& modules,
                       const std::vector<std::string>& inputs) {
  mozc::ImmutableConverter converter(modules);
  std::ofstream out(output_path);
  if (!out) {
    std::cerr << "Cannot open output: " << output_path << "\n";
    std::exit(1);
  }
  out << "{\n";
  out << "  \"engineDataVersion\": " << JsonString(modules.GetDataManager().GetDataVersion()) << ",\n";
  out << "  \"cases\": [\n";
  for (size_t i = 0; i < inputs.size(); ++i) {
    mozc::ConversionOptions conversion_options;
    conversion_options.request_type = mozc::RequestType::CONVERSION;
    conversion_options.max_conversion_candidates_size = 20;

    mozc::Segments segments;
    mozc::Lattice lattice;
    segments.InitForConvert(inputs[i]);
    if (!converter.Convert(conversion_options, &segments, &lattice)) {
      std::cerr << "NBest conversion failed for input: " << inputs[i] << "\n";
      std::exit(1);
    }

    out << "    {\n";
    out << "      \"input\": " << JsonString(inputs[i]) << ",\n";
    out << "      \"requestType\": \"CONVERSION\",\n";
    out << "      \"segments\": [\n";
    for (size_t segment_index = 0;
         segment_index < segments.conversion_segments_size();
         ++segment_index) {
      const mozc::Segment& segment = segments.conversion_segment(segment_index);
      out << "        {\n";
      out << "          \"index\": " << segment_index << ",\n";
      out << "          \"key\": " << JsonString(segment.key()) << ",\n";
      out << "          \"candidates\": [\n";
      for (size_t candidate_index = 0;
           candidate_index < segment.candidates_size(); ++candidate_index) {
        WriteCandidate(out, segment.candidate(candidate_index),
                       candidate_index, "            ");
        if (candidate_index + 1 != segment.candidates_size()) {
          out << ",";
        }
        out << "\n";
      }
      out << "          ]\n";
      out << "        }";
      if (segment_index + 1 != segments.conversion_segments_size()) {
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

void WriteCandidateFilterFixture(const std::string& output_path,
                                 const mozc::engine::Modules& modules,
                                 const std::vector<std::string>& inputs) {
  mozc::ImmutableConverter converter(modules);
  std::ofstream out(output_path);
  if (!out) {
    std::cerr << "Cannot open output: " << output_path << "\n";
    std::exit(1);
  }
  out << "{\n";
  out << "  \"engineDataVersion\": " << JsonString(modules.GetDataManager().GetDataVersion()) << ",\n";
  out << "  \"cases\": [\n";
  for (size_t i = 0; i < inputs.size(); ++i) {
    mozc::ConversionOptions conversion_options;
    conversion_options.request_type = mozc::RequestType::CONVERSION;
    conversion_options.max_conversion_candidates_size = 20;

    mozc::Segments segments;
    mozc::Lattice lattice;
    segments.InitForConvert(inputs[i]);
    if (!converter.Convert(conversion_options, &segments, &lattice)) {
      std::cerr << "CandidateFilter source conversion failed for input: "
                << inputs[i] << "\n";
      std::exit(1);
    }
    const std::vector<mozc::converter::Candidate> before =
        BuildBeforeFilter(FlattenCandidates(segments));
    const std::vector<mozc::converter::Candidate> after =
        ApplyOfficialCandidateFilter(modules, inputs[i], before);

    out << "    {\n";
    out << "      \"input\": " << JsonString(inputs[i]) << ",\n";
    out << "      \"beforeFilter\": [\n";
    for (size_t j = 0; j < before.size(); ++j) {
      WriteFilterCandidate(out, before[j], "        ");
      if (j + 1 != before.size()) {
        out << ",";
      }
      out << "\n";
    }
    out << "      ],\n";
    out << "      \"afterFilter\": [\n";
    for (size_t j = 0; j < after.size(); ++j) {
      WriteFilterCandidate(out, after[j], "        ");
      if (j + 1 != after.size()) {
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

  const std::vector<std::string> inputs = {
      "へんかん",
      "きょう",
      "ありがとう",
      "とうきょう",
      "にほんご",
      "わたしは",
      "これは",
      "かんじ",
      "やまだたろう",
      "123",
      "第一",
  };

  WriteNBestFixture(options.nbest_output_path, **modules, inputs);
  WriteCandidateFilterFixture(options.candidate_filter_output_path, **modules,
                              inputs);
  return 0;
}
