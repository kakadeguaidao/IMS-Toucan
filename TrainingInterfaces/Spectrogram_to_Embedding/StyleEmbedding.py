import numpy
import torch

from TrainingInterfaces.Spectrogram_to_Embedding.GST import StyleEncoder


class StyleEmbedding(torch.nn.Module):
    """
    The style embedding should provide information of the speaker and their speaking style

    The feedback signal for the module will come from the TTS objective, so it doesn't have a dedicated train loop.
    The train loop does however supply supervision in the form of a barlow twins objective.

    See the git history for some other approaches for style embedding, like the SWIN transformer
    and a simple LSTM baseline. GST turned out to be the best.
    """

    def __init__(self):
        super().__init__()
        self.gst = StyleEncoder()

    def forward(self,
                batch_of_spectrograms,
                batch_of_spectrogram_lengths,
                return_all_outs=False,
                return_only_refs=False):
        """
        Args:
            return_only_refs: return reference embedding instead of mixed style tokens
            batch_of_spectrograms: b is the batch axis, 80 features per timestep
                                   and l time-steps, which may include padding
                                   for most elements in the batch (b, l, 80)
            batch_of_spectrogram_lengths: indicate for every element in the batch,
                                          what the true length is, since they are
                                          all padded to the length of the longest
                                          element in the batch (b, 1)
            return_all_outs: boolean indicating whether the output will be used for a feature matching loss
        Returns:
            batch of 256 dimensional embeddings (b,256)
        """

        window_size = 256  # Zipf distribution suggests 64 would be best, because GST can actually get confused by padding. But that's too little information
        # on the time axis to accurately learn a style. So instead, we concatenate each spectrogram with itself until we reach at least 256.
        list_of_specs = list()
        for index, spec_length in enumerate(batch_of_spectrogram_lengths):
            spec = batch_of_spectrograms[index][:spec_length]
            # double the length at least once, then check
            spec = spec.repeat((2, 1))
            current_spec_length = len(spec)
            while current_spec_length < window_size:
                # make it longer
                spec = spec.repeat((2, 1))
                current_spec_length = len(spec)
            if current_spec_length > window_size:
                # take random window
                frames_to_remove = current_spec_length - window_size
                remove_front = numpy.random.randint(low=0, high=frames_to_remove)
                list_of_specs.append(spec[remove_front:remove_front + window_size])
            elif current_spec_length == window_size:
                # take as is
                list_of_specs.append(spec)

        batch_of_spectrograms_unified_length = torch.stack(list_of_specs, dim=0)
        return self.gst(batch_of_spectrograms_unified_length,
                        return_all_outs=return_all_outs,
                        return_only_ref=return_only_refs)


if __name__ == '__main__':
    style_emb = StyleEmbedding()
    print(f"GST parameter count: {sum(p.numel() for p in style_emb.gst.parameters() if p.requires_grad)}")

    seq_length = 142
    print(style_emb(torch.randn(5, seq_length, 80),
                    torch.tensor([seq_length, seq_length, seq_length, seq_length, seq_length]),
                    return_only_refs=False).shape)
    print(style_emb.gst.calculate_ada4_regularization_loss())
